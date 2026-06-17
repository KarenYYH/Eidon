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
