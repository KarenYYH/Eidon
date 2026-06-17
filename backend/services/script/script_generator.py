import json
import re
from loguru import logger

from core.config import settings


LANG_NAMES = {
    "zh": "中文", "en": "English", "ja": "日本語",
    "ko": "한국어", "es": "Español", "fr": "Français",
}


async def generate_script(topic: str, duration_sec: int, language: str) -> list[dict]:
    """
    Ask LLM to produce a scene-by-scene script.
    Returns list of: {narration, visual_keywords, duration}
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API Key 未配置，请在设置页面填写")

    lang_name = LANG_NAMES.get(language, language)
    scene_count = max(3, duration_sec // 10)

    system_prompt = (
        "You are a professional short-video script writer. "
        "Return ONLY valid JSON — no markdown, no code fences."
    )
    user_prompt = f"""Create a {duration_sec}-second video script about: "{topic}"
Language: {lang_name}
Scenes: {scene_count}

Return a JSON array of objects. Each object must have:
- "narration": spoken text for this scene ({lang_name})
- "visual_keywords": list of 3-5 English words describing the visuals
- "duration": seconds (integer, must sum to {duration_sec})

Example:
[
  {{"narration": "...", "visual_keywords": ["city", "night", "lights"], "duration": 8}},
  {{"narration": "...", "visual_keywords": ["people", "walking", "street"], "duration": 7}}
]"""

    from openai import AsyncOpenAI
    kwargs: dict = {"api_key": settings.LLM_API_KEY}
    if settings.LLM_BASE_URL:
        kwargs["base_url"] = settings.LLM_BASE_URL
    client = AsyncOpenAI(**kwargs)

    resp = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        response_format={"type": "json_object"} if _supports_json_mode() else None,
    )
    raw = resp.choices[0].message.content
    scenes = _parse_scenes(raw, scene_count, duration_sec)
    logger.info(f"Generated {len(scenes)} scenes for topic '{topic}'")
    return scenes


def _supports_json_mode() -> bool:
    m = settings.LLM_MODEL.lower()
    return any(x in m for x in ("gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"))


def _parse_scenes(raw: str, expected: int, total_sec: int) -> list[dict]:
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(raw)
        # LLM might wrap array in a key
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
        scenes = []
        for item in data:
            scenes.append({
                "narration": str(item.get("narration", "")),
                "visual_keywords": list(item.get("visual_keywords", [])),
                "duration": float(item.get("duration", total_sec / expected)),
            })
        if scenes:
            return scenes
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: single scene with the whole text
    return [{"narration": raw[:500], "visual_keywords": [], "duration": float(total_sec)}]
