import asyncio
import tempfile
import os
from pathlib import Path
from loguru import logger

from core.config import settings


async def transcribe(video_path: str, job_id: str, model_size: str = "base") -> str:
    out_dir = Path(settings.TEMP_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = str(out_dir / "subtitles.srt")

    logger.info(f"[{job_id}] Transcribing with Whisper ({model_size})")

    # Write helper script to system temp dir (outside project) to avoid
    # triggering uvicorn --reload on file changes inside the project tree
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(_build_whisper_script(video_path, srt_path, model_size))
        script_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    finally:
        os.unlink(script_path)

    if proc.returncode != 0:
        raise RuntimeError(f"Whisper failed: {stderr.decode()}")

    logger.info(f"[{job_id}] Transcription done: {srt_path}")
    return srt_path


def _build_whisper_script(video_path: str, srt_path: str, model_size: str) -> str:
    return f'''import whisper

def fmt(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t % 1) * 1000)
    return f"{{h:02d}}:{{m:02d}}:{{s:02d}},{{ms:03d}}"

model = whisper.load_model("{model_size}")
result = model.transcribe(r"{video_path}", task="transcribe")
segments = result["segments"]

with open(r"{srt_path}", "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        f.write(f"{{i}}\\n{{fmt(seg['start'])}} --> {{fmt(seg['end'])}}\\n{{seg['text'].strip()}}\\n\\n")

print(f"Done: {{len(segments)}} segments, language={{result.get('language')}}")
'''
