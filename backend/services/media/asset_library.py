"""Asset library for digital-human / voice-cloning reference files.

- voices/  : reference voice samples for CosyVoice zero-shot cloning (wav/mp3)
- avatars/ : reference face videos for HeyGem lip-sync (mp4/mov)
"""
from pathlib import Path

from core.config import settings

VOICE_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}
AVATAR_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _list(dir_path: str, exts: set[str]) -> list[dict]:
    d = Path(dir_path)
    items = []
    for f in sorted(d.iterdir()) if d.exists() else []:
        if f.suffix.lower() in exts:
            items.append({"name": f.name, "path": str(f), "size": f.stat().st_size})
    return items


def list_voices() -> list[dict]:
    return _list(settings.VOICES_DIR, VOICE_EXTS)


def list_avatars() -> list[dict]:
    return _list(settings.AVATARS_DIR, AVATAR_EXTS)
