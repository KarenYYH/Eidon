"""Integration test: runs the real translate pipeline against a local fixture
video. Whisper, edge-tts, and ffmpeg run for real; only the LLM translation
call is mocked so the test is offline-deterministic and needs no API key.

Marked 'slow' — Whisper transcription takes a few seconds. Skipped automatically
if ffmpeg is unavailable or the fixture video cannot be built.
"""
import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from models.job import Job, JobMode, JobStatus, JobStep
from core.task_manager import TaskManager
import services.translator.translator as translator_mod

pytestmark = pytest.mark.slow

BACKEND = Path(__file__).resolve().parent.parent
FIXTURE = BACKEND / "temp" / "_fixtures" / "test_video.mp4"


def _ensure_fixture_video() -> bool:
    if FIXTURE.exists():
        return True
    if not shutil.which("ffmpeg"):
        return False
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # 4s silent-ish tone video so Whisper has audio structure to chew on
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(FIXTURE)],
        capture_output=True,
    )
    return r.returncode == 0 and FIXTURE.exists()


@pytest.fixture
def fake_translate(monkeypatch):
    """Mock the LLM batch translator: echo each line with a [zh] prefix."""
    async def _fake_batch(texts, lang_name):
        return [f"[{lang_name}] {t}" for t in texts]
    monkeypatch.setattr(translator_mod, "_translate_batch", _fake_batch)


async def test_translate_pipeline_end_to_end(fake_translate, tmp_path, monkeypatch):
    if not _ensure_fixture_video():
        pytest.skip("ffmpeg unavailable; cannot build fixture video")

    # redirect output/temp dirs into tmp_path to avoid polluting real artifacts
    from core import config
    monkeypatch.setattr(config.settings, "OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))

    from services.pipeline import run_pipeline

    tm = TaskManager()
    job = Job(
        title="pytest e2e",
        mode=JobMode.TRANSLATE,
        source_file=str(FIXTURE),
        target_language="zh",
        tts_provider="edge",
    )
    tm.create_job(job)

    await run_pipeline(job, tm)

    # every step completed
    statuses = {s.step: s.status for s in job.steps}
    assert statuses[JobStep.DOWNLOAD] == JobStatus.COMPLETED
    assert statuses[JobStep.TRANSCRIBE] == JobStatus.COMPLETED
    assert statuses[JobStep.TRANSLATE] == JobStatus.COMPLETED
    assert statuses[JobStep.TTS] == JobStatus.COMPLETED
    assert statuses[JobStep.SYNTHESIZE] == JobStatus.COMPLETED

    # artifacts exist and are non-empty
    assert job.subtitle_file and Path(job.subtitle_file).exists()
    assert job.audio_file and Path(job.audio_file).stat().st_size > 0
    assert job.output_file and Path(job.output_file).stat().st_size > 0

    # translated subtitle carries the mock prefix
    srt = Path(job.subtitle_file).read_text(encoding="utf-8")
    assert "[Simplified Chinese]" in srt

    # output is a valid mp4 with a video stream
    if shutil.which("ffprobe"):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", job.output_file],
            capture_output=True, text=True,
        )
        assert "h264" in probe.stdout


async def test_translate_pipeline_fails_without_llm_key(monkeypatch, tmp_path):
    """When no API key is configured, the translate step must fail loudly."""
    if not _ensure_fixture_video():
        pytest.skip("ffmpeg unavailable")

    from core import config
    monkeypatch.setattr(config.settings, "OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(config.settings, "LLM_API_KEY", "")

    from services.translator.translator import translate_subtitles
    srt = tmp_path / "in.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="LLM API Key"):
        await translate_subtitles(str(srt), "zh", "jobid")
