"""Online stock-video material providers (Pexels / Pixabay free tiers).

Used by the CREATE pipeline to auto-download clips matching a scene's
visual_keywords when the local media library has no match. Downloaded clips
land in MEDIA_DIR so they're reused by future jobs (and findable by search_clips).
"""
import asyncio
import re
from pathlib import Path
from urllib.parse import urlencode

import httpx
from loguru import logger

from core.config import settings

ASPECT_ORIENTATION = {"9:16": "portrait", "16:9": "landscape", "1:1": "square"}


def is_enabled() -> bool:
    if not settings.STOCK_ENABLED:
        return False
    if settings.STOCK_PROVIDER == "pixabay":
        return bool(settings.PIXABAY_API_KEY)
    return bool(settings.PEXELS_API_KEY)


async def fetch_clip(keywords: list[str], aspect: str, job_id: str) -> str | None:
    """Search the configured provider for a clip matching keywords; download the
    first hit into MEDIA_DIR. Returns the local path, or None on miss/error."""
    if not is_enabled() or not keywords:
        return None
    query = " ".join(keywords[:3]).strip()
    if not query:
        return None
    try:
        if settings.STOCK_PROVIDER == "pixabay":
            url = await _search_pixabay(query, aspect)
        else:
            url = await _search_pexels(query, aspect)
        if not url:
            logger.info(f"[{job_id}] stock: no match for '{query}'")
            return None
        return await _download(url, query, job_id)
    except Exception as e:
        logger.warning(f"[{job_id}] stock fetch failed for '{query}': {e}")
        return None


async def _search_pexels(query: str, aspect: str) -> str | None:
    orientation = ASPECT_ORIENTATION.get(aspect, "portrait")
    params = {"query": query, "per_page": 10, "orientation": orientation}
    url = f"https://api.pexels.com/videos/search?{urlencode(params)}"
    headers = {"Authorization": settings.PEXELS_API_KEY}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
    videos = data.get("videos") or []
    for v in videos:
        files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
        for f in files:
            if f.get("link"):
                return f["link"]
    return None


async def _search_pixabay(query: str, aspect: str) -> str | None:
    params = {"q": query, "video_type": "all", "per_page": 10, "key": settings.PIXABAY_API_KEY}
    url = f"https://pixabay.com/api/videos/?{urlencode(params)}"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url)
        r.raise_for_status()
        data = r.json()
    for hit in data.get("hits") or []:
        videos = hit.get("videos") or {}
        for quality in ("large", "medium", "small", "tiny"):
            v = videos.get(quality)
            if v and v.get("url"):
                return v["url"]
    return None


async def _download(url: str, query: str, job_id: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_") or "stock"
    dest = Path(settings.MEDIA_DIR) / f"stock_{safe}_{abs(hash(url)) % 10**8}.mp4"
    if dest.exists():
        return str(dest)
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
        async with c.stream("GET", url) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                async for chunk in r.aiter_bytes(65536):
                    f.write(chunk)
    logger.info(f"[{job_id}] stock downloaded: {dest.name}")
    return str(dest)
