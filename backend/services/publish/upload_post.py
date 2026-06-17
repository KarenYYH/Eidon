"""Multi-platform publishing via upload-post.com.

Uploads a finished video to one or more social platforms (TikTok, Instagram,
YouTube, etc.) in a single API call. Requires UPLOAD_POST_API_KEY.

NOTE: this performs a real outbound upload of the user's video to a third-party
service — only invoked when a job explicitly lists publish_platforms.
"""
from pathlib import Path

import httpx
from loguru import logger

from core.config import settings


def is_configured() -> bool:
    return bool(settings.UPLOAD_POST_API_KEY)


async def publish_video(video_path: str, title: str, platforms: list[str], job_id: str) -> dict:
    """Upload `video_path` to the given platforms. Returns the service response."""
    if not is_configured():
        raise RuntimeError("发布功能需要配置 UPLOAD_POST_API_KEY")
    if not video_path or not Path(video_path).exists():
        raise RuntimeError("发布失败：成片文件不存在")
    if not platforms:
        raise ValueError("未指定发布平台")

    url = f"{settings.UPLOAD_POST_HOST}/api/upload_video"
    headers = {"Authorization": f"Apikey {settings.UPLOAD_POST_API_KEY}"}
    data = {"title": title or "Eidon video", "platform[]": platforms}

    logger.info(f"[{job_id}] Publishing to {platforms}")
    with Path(video_path).open("rb") as f:
        files = {"video": (Path(video_path).name, f, "video/mp4")}
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
            resp.raise_for_status()
            result = resp.json()

    logger.info(f"[{job_id}] Publish response: {result}")
    return result
