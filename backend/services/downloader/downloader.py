import asyncio
import os
from pathlib import Path
from loguru import logger

from core.config import settings


async def download_video(source: str, job_id: str) -> str:
    out_dir = Path(settings.TEMP_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "video.%(ext)s")

    if source.startswith("http://") or source.startswith("https://"):
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--merge-output-format", "mp4",
            "-o", out_template,
            source,
        ]
        logger.info(f"[{job_id}] Downloading: {source}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {stderr.decode()}")

        # Find downloaded file
        for f in out_dir.iterdir():
            if f.suffix in (".mp4", ".mkv", ".webm", ".mov"):
                logger.info(f"[{job_id}] Downloaded to {f}")
                return str(f)
        raise RuntimeError("Downloaded file not found")

    # Local file path
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")

    # Copy to temp dir
    dst = out_dir / Path(source).name
    import shutil
    shutil.copy2(source, dst)
    return str(dst)
