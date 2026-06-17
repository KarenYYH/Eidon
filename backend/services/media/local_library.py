import os
import random
from pathlib import Path
from loguru import logger

from core.config import settings

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def list_clips() -> list[dict]:
    media_dir = Path(settings.MEDIA_DIR)
    clips = []
    for f in sorted(media_dir.iterdir()):
        if f.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS:
            clips.append({
                "name": f.name,
                "path": str(f),
                "type": "video" if f.suffix.lower() in VIDEO_EXTS else "image",
                "size": f.stat().st_size,
            })
    return clips


def search_clips(keywords: list[str], count: int = 3) -> list[str]:
    """Return up to `count` clip paths whose filenames match any keyword."""
    all_clips = [
        f for f in Path(settings.MEDIA_DIR).iterdir()
        if f.suffix.lower() in VIDEO_EXTS | IMAGE_EXTS
    ]
    if not all_clips:
        return []

    scored: list[tuple[int, Path]] = []
    for clip in all_clips:
        stem = clip.stem.lower().replace("-", " ").replace("_", " ")
        score = sum(1 for kw in keywords if kw.lower() in stem)
        scored.append((score, clip))

    scored.sort(key=lambda x: -x[0])
    # Top matches first; if no match, fall back to random selection
    result = [str(p) for _, p in scored if _ > 0][:count]
    if len(result) < count:
        remaining = [str(p) for s, p in scored if s == 0]
        random.shuffle(remaining)
        result += remaining[: count - len(result)]
    return result


def list_bgm() -> list[dict]:
    bgm_dir = Path(settings.BGM_DIR)
    tracks = []
    for f in sorted(bgm_dir.iterdir()):
        if f.suffix.lower() in AUDIO_EXTS:
            tracks.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
            })
    return tracks


def get_random_bgm() -> str | None:
    tracks = list_bgm()
    if not tracks:
        return None
    return random.choice(tracks)["path"]
