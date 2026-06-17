import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List

from core.config import settings
from services.media.local_library import list_clips, list_bgm, search_clips

router = APIRouter()


@router.get("/clips")
async def get_clips():
    return list_clips()


@router.get("/bgm")
async def get_bgm():
    return list_bgm()


class SearchRequest(BaseModel):
    keywords: List[str]
    count: int = 3


@router.post("/search")
async def search_media(req: SearchRequest):
    results = search_clips(req.keywords, req.count)
    return [{"path": p, "name": Path(p).name} for p in results]


@router.post("/upload/clip")
async def upload_clip(file: UploadFile = File(...)):
    dest = Path(settings.MEDIA_DIR) / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"name": file.filename, "path": str(dest)}


@router.post("/upload/bgm")
async def upload_bgm(file: UploadFile = File(...)):
    dest = Path(settings.BGM_DIR) / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"name": file.filename, "path": str(dest)}


@router.delete("/clip/{filename}")
async def delete_clip(filename: str):
    path = Path(settings.MEDIA_DIR) / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    path.unlink()
    return {"status": "deleted"}


@router.delete("/bgm/{filename}")
async def delete_bgm(filename: str):
    path = Path(settings.BGM_DIR) / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    path.unlink()
    return {"status": "deleted"}
