import shutil
import re
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from core.config import settings

router = APIRouter()

EDGE_TTS_VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓 (中文女声)", "lang": "zh"},
    {"id": "zh-CN-YunxiNeural", "name": "云希 (中文男声)", "lang": "zh"},
    {"id": "zh-CN-YunjianNeural", "name": "云健 (中文男声)", "lang": "zh"},
    {"id": "zh-TW-HsiaoChenNeural", "name": "曉臻 (繁中女声)", "lang": "zh-TW"},
    {"id": "en-US-JennyNeural", "name": "Jenny (EN Female)", "lang": "en"},
    {"id": "en-US-GuyNeural", "name": "Guy (EN Male)", "lang": "en"},
    {"id": "ja-JP-NanamiNeural", "name": "七海 (日文女声)", "lang": "ja"},
    {"id": "ko-KR-SunHiNeural", "name": "선히 (韩文女声)", "lang": "ko"},
]


class LLMConfigRequest(BaseModel):
    api_key: str
    base_url: Optional[str] = ""
    model: Optional[str] = "gpt-4o-mini"


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@router.get("/voices")
async def list_voices():
    return EDGE_TTS_VOICES


@router.get("/tools")
async def check_tools():
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "whisper": _check_python_pkg("whisper"),
        "edge_tts": _check_python_pkg("edge_tts"),
        "pydub": _check_python_pkg("pydub"),
        "cosyvoice": await _check_service(settings.COSYVOICE_HOST),
        "heygem": await _check_service(settings.HEYGEM_HOST),
        "stock": settings.STOCK_ENABLED and bool(
            settings.PIXABAY_API_KEY if settings.STOCK_PROVIDER == "pixabay" else settings.PEXELS_API_KEY
        ),
        "publish": bool(settings.UPLOAD_POST_API_KEY),
    }


async def _check_service(host: str) -> bool:
    """Best-effort reachability check for an external HTTP service."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            await client.get(host)
        return True
    except Exception:
        return False


@router.get("/config")
async def get_config():
    key = settings.LLM_API_KEY
    masked = (key[:8] + "..." + key[-4:]) if len(key) > 12 else ("***" if key else "")
    return {
        "api_key_masked": masked,
        "api_key_set": bool(key),
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
    }


@router.post("/config")
async def save_config(req: LLMConfigRequest):
    env_path = Path(settings.BASE_DIR) / ".env"
    _write_env(env_path, {
        "LLM_API_KEY": req.api_key,
        "LLM_BASE_URL": req.base_url or "",
        "LLM_MODEL": req.model or "gpt-4o-mini",
    })
    # Hot-reload settings in memory
    settings.LLM_API_KEY = req.api_key
    settings.LLM_BASE_URL = req.base_url or ""
    settings.LLM_MODEL = req.model or "gpt-4o-mini"
    return {"status": "saved"}


@router.post("/test-llm")
async def test_llm(req: LLMConfigRequest):
    try:
        from openai import AsyncOpenAI
        kwargs: dict = {"api_key": req.api_key}
        if req.base_url:
            kwargs["base_url"] = req.base_url
        client = AsyncOpenAI(**kwargs)
        resp = await client.chat.completions.create(
            model=req.model or "gpt-4o-mini",
            messages=[{"role": "user", "content": "Reply with just: OK"}],
            max_tokens=10,
        )
        return {"status": "ok", "reply": resp.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _check_python_pkg(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def _write_env(path: Path, updates: dict[str, str]):
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing_keys = set()
    new_lines = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            existing_keys.add(key)
        else:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in existing_keys:
            new_lines.append(f"{k}={v}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
