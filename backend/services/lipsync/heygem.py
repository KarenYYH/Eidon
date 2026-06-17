"""HeyGem digital-human (lip-sync) integration.

Targets the open-source Duix.Heygem face2face HTTP service. It is asynchronous:
submit a job with an audio track + a reference face video, then poll until the
synthesized talking-head video is ready, and finally fetch the result.

NOTE: HeyGem runs as a separate (Windows/Docker, GPU) service. This module only
speaks its HTTP contract; nothing here runs locally on this machine.
"""
import asyncio
import uuid
from pathlib import Path

import httpx
from loguru import logger

from core.config import settings


async def generate_digital_human(audio_path: str, avatar_video: str, job_id: str) -> str:
    """Synthesize a lip-synced talking-head video from `audio_path` driving the
    face in `avatar_video`. Returns the path to the downloaded result video."""
    if not audio_path or not Path(audio_path).exists():
        raise RuntimeError("数字人合成需要音频文件，但未提供或不存在")
    if not avatar_video or not Path(avatar_video).exists():
        raise RuntimeError("数字人合成需要人脸参考视频 (avatar_video)，但未提供或不存在")

    code = f"eidon_{job_id}_{uuid.uuid4().hex[:8]}"
    out_dir = Path(settings.TEMP_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output = str(out_dir / "digital_human.mp4")

    async with httpx.AsyncClient(timeout=60) as client:
        await _submit(client, code, audio_path, avatar_video, job_id)
        result_url = await _poll(client, code, job_id)
        await _download(client, result_url, output, job_id)

    logger.info(f"[{job_id}] Digital-human video: {output}")
    return output


async def _submit(client: httpx.AsyncClient, code: str, audio_path: str,
                  avatar_video: str, job_id: str):
    """POST /easy/submit — register a face2face synthesis job."""
    payload = {
        "code": code,
        "audio_url": audio_path,
        "video_url": avatar_video,
        "chaofen": 0,            # super-resolution off by default
        "watermark_switch": 0,
        "pn": 1,
    }
    logger.info(f"[{job_id}] HeyGem submit (code={code})")
    resp = await client.post(f"{settings.HEYGEM_HOST}/easy/submit", json=payload)
    resp.raise_for_status()
    body = resp.json()
    # Duix.Heygem returns {"code": 10000, "success": true, ...} on accept
    if not _is_ok(body):
        raise RuntimeError(f"HeyGem submit rejected: {body}")


async def _poll(client: httpx.AsyncClient, code: str, job_id: str) -> str:
    """GET /easy/query — poll until status is complete; return result video URL/path."""
    deadline = asyncio.get_event_loop().time() + settings.HEYGEM_TIMEOUT
    while True:
        resp = await client.get(f"{settings.HEYGEM_HOST}/easy/query", params={"code": code})
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body) or {}
        status = data.get("status")

        # Duix.Heygem status: 1=pending/running, 2=success, 3=failed
        if status == 2 or data.get("result"):
            result = data.get("result") or data.get("video_url") or data.get("url")
            if not result:
                raise RuntimeError(f"HeyGem finished but returned no result URL: {body}")
            return result
        if status == 3 or _is_failed(body):
            raise RuntimeError(f"HeyGem synthesis failed: {body}")

        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(
                f"HeyGem job {code} did not finish within {settings.HEYGEM_TIMEOUT}s"
            )
        await asyncio.sleep(settings.HEYGEM_POLL_INTERVAL)


async def _download(client: httpx.AsyncClient, result: str, output: str, job_id: str):
    """Fetch the result. `result` may be an http(s) URL or a server-local path."""
    if result.startswith("http://") or result.startswith("https://"):
        resp = await client.get(result)
        resp.raise_for_status()
        Path(output).write_bytes(resp.content)
        return
    # Server-local path: only usable when HeyGem shares this filesystem.
    src = Path(result)
    if src.exists():
        import shutil
        shutil.copy2(src, output)
        return
    raise RuntimeError(
        f"HeyGem result is a path not reachable from this host: {result}. "
        "配置 HeyGem 返回可下载 URL，或与其共享文件系统。"
    )


def _is_ok(body: dict) -> bool:
    return body.get("success") is True or body.get("code") in (0, 10000, 200)


def _is_failed(body: dict) -> bool:
    return body.get("success") is False and body.get("code") not in (0, 10000, 200)
