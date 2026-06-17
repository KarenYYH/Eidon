"""Integration test for the digital-human pipeline (both external calls mocked).

The TTS step uses real edge-tts (network) when available; the HeyGem lip-sync
call is always mocked. Marked 'slow' because of the edge-tts round-trip.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from models.job import Job, JobMode, JobStatus, JobStep
from core.task_manager import TaskManager
import services.lipsync.heygem as hg

pytestmark = pytest.mark.slow


@pytest.fixture
def fake_heygem(monkeypatch):
    async def _fake(audio_path, avatar_video, job_id):
        # assert the pipeline passed a real audio file and the avatar through
        assert Path(audio_path).exists()
        assert avatar_video and Path(avatar_video).exists()
        out = Path(audio_path).parent / "digital_human.mp4"
        out.write_bytes(b"FAKE_DH_VIDEO")
        return str(out)
    monkeypatch.setattr(hg, "generate_digital_human", _fake)
    # pipeline imports the symbol lazily, so also patch the pipeline's reference
    import services.pipeline as pl
    monkeypatch.setattr("services.lipsync.heygem.generate_digital_human", _fake, raising=False)


async def test_digital_human_pipeline_edge(fake_heygem, monkeypatch, tmp_path):
    from core import config
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))

    avatar = tmp_path / "face.mp4"
    avatar.write_bytes(b"fake mp4")

    from services.pipeline import run_pipeline
    tm = TaskManager()
    job = Job(
        title="dh test", mode=JobMode.DIGITAL_HUMAN,
        text="大家好，这是数字人测试。", avatar_video=str(avatar), tts_provider="edge",
    )
    tm.create_job(job)
    await run_pipeline(job, tm)

    statuses = {s.step: s.status for s in job.steps}
    assert statuses[JobStep.TTS] == JobStatus.COMPLETED
    assert statuses[JobStep.LIPSYNC] == JobStatus.COMPLETED
    assert job.output_file and Path(job.output_file).read_bytes() == b"FAKE_DH_VIDEO"


async def test_digital_human_supplied_audio_skips_tts(fake_heygem, monkeypatch, tmp_path):
    from core import config
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))
    avatar = tmp_path / "face.mp4"; avatar.write_bytes(b"x")
    audio = tmp_path / "given.wav"; audio.write_bytes(b"RIFFfake")

    from services.pipeline import run_pipeline
    tm = TaskManager()
    job = Job(mode=JobMode.DIGITAL_HUMAN, avatar_video=str(avatar), audio_file=str(audio))
    tm.create_job(job)
    await run_pipeline(job, tm)

    tts_step = job.get_step(JobStep.TTS)
    assert tts_step.message == "Using supplied audio"
    assert job.output_file and Path(job.output_file).exists()


async def test_digital_human_requires_text_or_audio(fake_heygem, monkeypatch, tmp_path):
    from core import config
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))
    avatar = tmp_path / "face.mp4"; avatar.write_bytes(b"x")

    from services.pipeline import run_pipeline
    tm = TaskManager()
    job = Job(mode=JobMode.DIGITAL_HUMAN, avatar_video=str(avatar), text="")
    tm.create_job(job)
    with pytest.raises(ValueError, match="文稿"):
        await run_pipeline(job, tm)
