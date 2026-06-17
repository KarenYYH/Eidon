"""Routes for digital-human assets: voice-clone samples and avatar face videos."""
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

from core.config import settings
from services.media.asset_library import (
    list_voices, list_avatars, VOICE_EXTS, AVATAR_EXTS,
)

router = APIRouter()


@router.get("/voices")
async def get_voices():
    return list_voices()


@router.get("/avatars")
async def get_avatars():
    return list_avatars()


@router.post("/upload/voice")
async def upload_voice(file: UploadFile = File(...)):
    if Path(file.filename).suffix.lower() not in VOICE_EXTS:
        raise HTTPException(400, f"Unsupported voice format: {file.filename}")
    dest = Path(settings.VOICES_DIR) / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"name": file.filename, "path": str(dest), "size": dest.stat().st_size}


@router.post("/upload/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    if Path(file.filename).suffix.lower() not in AVATAR_EXTS:
        raise HTTPException(400, f"Unsupported avatar format: {file.filename}")
    dest = Path(settings.AVATARS_DIR) / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"name": file.filename, "path": str(dest), "size": dest.stat().st_size}


@router.delete("/voice/{filename}")
async def delete_voice(filename: str):
    path = Path(settings.VOICES_DIR) / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    path.unlink()
    return {"status": "deleted"}


@router.delete("/avatar/{filename}")
async def delete_avatar(filename: str):
    path = Path(settings.AVATARS_DIR) / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    path.unlink()
    return {"status": "deleted"}
