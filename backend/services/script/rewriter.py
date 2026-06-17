"""Rewrite an existing spoken-script (transcript) into N fresh narration scripts
via the LLM. Used by the REWRITE (batch) pipeline.
"""
import json
import re
from loguru import logger

from core.config import settings

LANG_NAMES = {
    "zh": "中文", "en": "English", "ja": "日本語",
    "ko": "한국어", "es": "Español", "fr": "Français",
}


async def rewrite_scripts(
    original_text: str,
    count: int,
    style: str = "",
    language: str = "zh",
) -> list[str]:
    """Produce `count` rewritten narration scripts based on `original_text`.

    `style` is a free-text angle/style instruction (e.g. "换个开头钩子，第一人称").
    Returns a list of plain-text scripts (length == count, best effort).
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API Key 未配置，请在设置页面填写")
    if not original_text.strip():
        raise ValueError("原始口播稿为空，无法改写")

    count = max(1, min(count, 20))
    lang_name = LANG_NAMES.get(language, language)
    style_clause = f"\n额外风格/角度要求：{style}" if style.strip() else ""

    system_prompt = (
        "你是资深短视频口播稿撰稿人。基于给定的原始口播内容，创作全新的口播稿，"
        "保留核心信息但表达、结构、开头钩子要有新意。只返回 JSON，不要 markdown、不要解释。"
    )
    user_prompt = (
        f"原始口播稿：\n\"\"\"\n{original_text.strip()}\n\"\"\"\n\n"
        f"请基于以上内容，用{lang_name}创作 {count} 条**不同的**全新口播稿。"
        f"每条都应可独立成片、适合口播。{style_clause}\n\n"
        f'返回 JSON 格式：{{"scripts": ["第一条…", "第二条…"]}}，数组长度为 {count}。'
    )

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
        temperature=0.8,
    )
    raw = resp.choices[0].message.content
    scripts = _parse_scripts(raw, count)
    logger.info(f"Rewrote into {len(scripts)} scripts (requested {count})")
    return scripts


async def rewrite_scripts_with_scenes(
    original_text: str,
    count: int,
    style: str = "",
    language: str = "zh",
    duration_sec: int = 60,
) -> list[list[dict]]:
    """Like `rewrite_scripts`, but each rewritten script also comes with visual
    scenes so it can become a stock-footage video (no digital human).

    Returns a list (length == count) of scene-lists; each scene-list is
    [{"narration": str, "duration": float, "visual_keywords": [str, ...]}, ...].
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API Key 未配置，请在设置页面填写")
    if not original_text.strip():
        raise ValueError("原始口播稿为空，无法改写")

    count = max(1, min(count, 20))
    lang_name = LANG_NAMES.get(language, language)
    style_clause = f"\n额外风格/角度要求：{style}" if style.strip() else ""

    system_prompt = (
        "你是资深短视频口播稿撰稿人兼分镜师。基于给定的原始口播内容，创作全新的口播稿，"
        "并为每条稿件切分镜头、给出画面检索关键词（英文，用于检索在线空镜素材）。"
        "只返回 JSON，不要 markdown、不要解释。"
    )
    user_prompt = (
        f"原始口播稿：\n\"\"\"\n{original_text.strip()}\n\"\"\"\n\n"
        f"请基于以上内容，用{lang_name}创作 {count} 条**不同的**全新口播稿，每条约 {duration_sec} 秒。"
        f"每条切成若干镜头(scene)，每个镜头给口播文字、时长(秒)、画面英文关键词。{style_clause}\n\n"
        f'返回 JSON：{{"scripts": [{{"scenes": [{{"narration": "…", "duration": 5, '
        f'"visual_keywords": ["city", "sunrise"]}}]}}]}}，scripts 数组长度为 {count}。'
    )

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
        temperature=0.8,
    )
    raw = resp.choices[0].message.content
    scripts = _parse_script_scenes(raw, count, duration_sec)
    logger.info(f"Rewrote into {len(scripts)} scripted scene-lists (requested {count})")
    return scripts


def _parse_script_scenes(raw: str, count: int, duration_sec: int) -> list[list[dict]]:
    """Parse the scenes-per-script JSON; tolerate shape drift. Falls back to a
    single-scene script (no keywords → assemble_scenes degrades to a text clip)."""
    raw = re.sub(r"```(?:json)?", "", raw or "").strip()
    out: list[list[dict]] = []
    try:
        data = json.loads(raw)
        scripts = data.get("scripts") if isinstance(data, dict) else data
        if isinstance(scripts, list):
            for item in scripts:
                scenes = item.get("scenes") if isinstance(item, dict) else item
                if not isinstance(scenes, list):
                    continue
                norm = []
                for sc in scenes:
                    if not isinstance(sc, dict):
                        continue
                    narration = str(sc.get("narration", "")).strip()
                    if not narration:
                        continue
                    kw = sc.get("visual_keywords") or []
                    if isinstance(kw, str):
                        kw = [kw]
                    norm.append({
                        "narration": narration,
                        "duration": float(sc.get("duration", 0) or 0),
                        "visual_keywords": [str(k) for k in kw if str(k).strip()],
                    })
                if norm:
                    out.append(norm)
    except (json.JSONDecodeError, TypeError, AttributeError, ValueError):
        pass

    if out:
        return out[:count]
    plain = _parse_scripts(raw, count)
    return [[{"narration": p, "duration": float(duration_sec), "visual_keywords": []}] for p in plain]


def _parse_scripts(raw: str, count: int) -> list[str]:
    raw = re.sub(r"```(?:json)?", "", raw or "").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # find the first list value (e.g. {"scripts": [...]})
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
        if isinstance(data, list):
            scripts = [str(s).strip() for s in data if str(s).strip()]
            if scripts:
                return scripts[:count]
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: split on blank lines / numbered markers
    parts = re.split(r"\n\s*\n|\n\d+[\.、)]\s*", raw)
    scripts = [p.strip() for p in parts if p.strip()]
    return scripts[:count] if scripts else [raw[:1000]]
