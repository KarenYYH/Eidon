"""Integration test for the REWRITE (batch) pipeline. All external calls
(download, Whisper, LLM rewrite) are mocked; verifies N digital-human child
jobs are spawned with the right fields and parent/child linkage.
"""
from pathlib import Path

import pytest

from models.job import Job, JobMode, JobStatus, JobStep
from core.task_manager import TaskManager
import services.pipeline as pl


@pytest.fixture
def mock_front_half(monkeypatch, tmp_path):
    """Mock download → transcribe → rewrite so no network/Whisper/LLM is needed."""
    async def fake_download(source, job_id):
        v = tmp_path / f"{job_id}.mp4"; v.write_bytes(b"video"); return str(v)

    async def fake_transcribe(video_path, job_id, model):
        srt = tmp_path / f"{job_id}.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n原始口播内容\n", encoding="utf-8")
        return str(srt)

    async def fake_rewrite(text, count, style, language):
        return [f"改写稿 {i+1}" for i in range(count)]

    monkeypatch.setattr("services.downloader.downloader.download_video", fake_download)
    monkeypatch.setattr("services.transcriber.whisper_stt.transcribe", fake_transcribe)
    monkeypatch.setattr("services.script.rewriter.rewrite_scripts", fake_rewrite)


async def test_rewrite_spawns_n_children(mock_front_half, monkeypatch, tmp_path):
    from core import config
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))

    tm = TaskManager()
    parent = Job(
        title="批量改写", mode=JobMode.REWRITE,
        source_url="http://example.com/v.mp4",
        script_count=3, rewrite_style="第一人称",
        avatar_video="/assets/face.mp4",
        tts_provider="cosyvoice", voice="", prompt_audio="/v/ref.wav", prompt_text="参考稿",
        script_language="zh",
    )
    tm.create_job(parent)
    await pl.run_pipeline(parent, tm)

    # parent steps all completed
    statuses = {s.step: s.status for s in parent.steps}
    assert statuses[JobStep.DOWNLOAD] == JobStatus.COMPLETED
    assert statuses[JobStep.TRANSCRIBE] == JobStatus.COMPLETED
    assert statuses[JobStep.REWRITE] == JobStatus.COMPLETED
    assert statuses[JobStep.DISPATCH] == JobStatus.COMPLETED

    # 3 scripts → 3 children
    assert len(parent.scripts) == 3
    assert len(parent.child_ids) == 3

    for cid, expected in zip(parent.child_ids, parent.scripts):
        child = tm.get_job(cid)
        assert child is not None
        assert child.mode == JobMode.DIGITAL_HUMAN
        assert child.text == expected
        assert child.parent_id == parent.id
        # cloning + avatar settings propagated
        assert child.avatar_video == "/assets/face.mp4"
        assert child.tts_provider == "cosyvoice"
        assert child.prompt_audio == "/v/ref.wav"
        assert child.prompt_text == "参考稿"


async def test_rewrite_extracts_plain_text(tmp_path):
    srt = tmp_path / "s.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n第一句\n\n2\n00:00:02,000 --> 00:00:04,000\n第二句\n",
        encoding="utf-8",
    )
    text = pl._srt_to_plain_text(str(srt))
    assert text == "第一句 第二句"


async def test_rewrite_stock_video_spawns_stock_children(monkeypatch, tmp_path):
    """output_kind=stock_video → children are STOCK_VIDEO jobs carrying scenes,
    no avatar needed."""
    from core import config
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))

    async def fake_download(source, job_id):
        v = tmp_path / f"{job_id}.mp4"; v.write_bytes(b"v"); return str(v)

    async def fake_transcribe(video_path, job_id, model):
        srt = tmp_path / f"{job_id}.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n原始\n", encoding="utf-8")
        return str(srt)

    async def fake_rewrite_scenes(text, count, style, language):
        return [[{"narration": f"稿{i+1}", "duration": 5, "visual_keywords": ["city"]}]
                for i in range(count)]

    monkeypatch.setattr("services.downloader.downloader.download_video", fake_download)
    monkeypatch.setattr("services.transcriber.whisper_stt.transcribe", fake_transcribe)
    monkeypatch.setattr("services.script.rewriter.rewrite_scripts_with_scenes", fake_rewrite_scenes)

    tm = TaskManager()
    parent = Job(
        title="洗稿", mode=JobMode.REWRITE, source_url="http://x/v.mp4",
        script_count=2, output_kind="stock_video", script_language="zh",
        bgm_enabled=True, video_aspect="9:16",
    )
    tm.create_job(parent)
    await pl.run_pipeline(parent, tm)

    assert len(parent.child_ids) == 2
    assert len(parent.script_scenes) == 2
    for cid in parent.child_ids:
        child = tm.get_job(cid)
        assert child is not None
        assert child.mode == JobMode.STOCK_VIDEO
        assert child.parent_id == parent.id
        assert child.scenes and child.scenes[0]["visual_keywords"] == ["city"]
        assert child.avatar_video is None       # no face needed
        assert child.bgm_enabled is True
        assert child.video_aspect == "9:16"
