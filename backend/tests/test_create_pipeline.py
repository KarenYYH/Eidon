"""Integration test for the CREATE pipeline: topic → script → tts → assemble → mix.
The LLM script generation is mocked (deterministic scenes); edge-tts and ffmpeg
run for real. Sample media clips are created on the fly so the clip-matching path
(search_clips → trim/loop → concat) is exercised rather than only the fallback.

Marked 'slow'. Skipped if ffmpeg is unavailable.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from models.job import Job, JobMode, JobStatus, JobStep
from core.task_manager import TaskManager
import services.script.script_generator as script_mod

pytestmark = pytest.mark.slow

_FAKE_SCENES = [
    {"narration": "人工智能正在重塑教育。", "visual_keywords": ["classroom", "student"], "duration": 4.0},
    {"narration": "数据分析帮助因材施教。", "visual_keywords": ["analytics", "data"], "duration": 4.0},
]


@pytest.fixture
def fake_script(monkeypatch):
    async def _fake(topic, duration_sec, language):
        return [dict(s) for s in _FAKE_SCENES]
    monkeypatch.setattr(script_mod, "generate_script", _fake)
    # pipeline imports the symbol lazily inside the function, so patching the
    # module attribute is sufficient.


def _make_media(media_dir: Path):
    media_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(media_dir / "classroom_student.mp4")],
        capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x240:d=1",
         "-frames:v", "1", str(media_dir / "analytics_data.png")],
        capture_output=True,
    )


async def test_create_pipeline_end_to_end(fake_script, monkeypatch, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")

    from core import config
    media_dir = tmp_path / "media"
    _make_media(media_dir)
    monkeypatch.setattr(config.settings, "OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(config.settings, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(config.settings, "MEDIA_DIR", str(media_dir))

    from services.pipeline import run_pipeline

    tm = TaskManager()
    job = Job(
        title="pytest create",
        mode=JobMode.CREATE,
        topic="人工智能如何改变教育",
        duration_sec=8,
        script_language="zh",
        tts_provider="edge",
    )
    tm.create_job(job)

    await run_pipeline(job, tm)

    statuses = {s.step: s.status for s in job.steps}
    assert statuses[JobStep.SCRIPT] == JobStatus.COMPLETED
    assert statuses[JobStep.TTS] == JobStatus.COMPLETED
    assert statuses[JobStep.ASSEMBLE] == JobStatus.COMPLETED
    assert statuses[JobStep.SYNTHESIZE] == JobStatus.COMPLETED

    assert len(job.scenes) == 2
    assert job.audio_file and Path(job.audio_file).stat().st_size > 0
    assert job.output_file and Path(job.output_file).stat().st_size > 0

    # output is a valid vertical mp4 with both streams
    if shutil.which("ffprobe"):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", job.output_file],
            capture_output=True, text=True,
        )
        assert "video" in probe.stdout and "audio" in probe.stdout


async def test_create_pipeline_fails_without_llm_key(monkeypatch):
    """Script generation must fail loudly when no API key is configured."""
    from core import config
    monkeypatch.setattr(config.settings, "LLM_API_KEY", "")
    from services.script.script_generator import generate_script
    with pytest.raises(RuntimeError, match="LLM API Key"):
        await generate_script("topic", 30, "zh")
