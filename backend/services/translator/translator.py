import re
from pathlib import Path
from loguru import logger

from core.config import settings


LANG_NAMES = {
    "zh": "Simplified Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ru": "Russian",
    "pt": "Portuguese",
    "ar": "Arabic",
}


def parse_srt(srt_text: str) -> list[dict]:
    blocks = re.split(r"\n\n+", srt_text.strip())
    segments = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0])
            timecode = lines[1]
            text = " ".join(lines[2:])
            segments.append({"index": idx, "timecode": timecode, "text": text})
        except ValueError:
            continue
    return segments


def build_srt(segments: list[dict]) -> str:
    parts = []
    for seg in segments:
        parts.append(f"{seg['index']}\n{seg['timecode']}\n{seg['text']}\n")
    return "\n".join(parts)


def _make_openai_client():
    from openai import AsyncOpenAI
    kwargs: dict = {"api_key": settings.LLM_API_KEY or "sk-placeholder"}
    if settings.LLM_BASE_URL:
        kwargs["base_url"] = settings.LLM_BASE_URL
    return AsyncOpenAI(**kwargs)


async def translate_subtitles(srt_path: str, target_lang: str, job_id: str) -> str:
    out_dir = Path(srt_path).parent
    out_path = str(out_dir / f"subtitles_{target_lang}.srt")

    srt_text = Path(srt_path).read_text(encoding="utf-8")
    segments = parse_srt(srt_text)

    if not segments:
        raise ValueError("No segments found in SRT file")

    lang_name = LANG_NAMES.get(target_lang, target_lang)
    logger.info(f"[{job_id}] Translating {len(segments)} segments to {lang_name}")

    batch_size = 50
    translated_segments = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        texts = [s["text"] for s in batch]
        translated_texts = await _translate_batch(texts, lang_name)
        for seg, translated in zip(batch, translated_texts):
            translated_segments.append({
                "index": seg["index"],
                "timecode": seg["timecode"],
                "text": translated,
            })

    Path(out_path).write_text(build_srt(translated_segments), encoding="utf-8")
    logger.info(f"[{job_id}] Translation saved to {out_path}")
    return out_path


async def _translate_batch(texts: list[str], lang_name: str) -> list[str]:
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API Key 未配置，请在设置页面填写")

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = (
        f"Translate the following subtitle lines to {lang_name}. "
        "Keep the same numbered format. Only output the translations, no explanations.\n\n"
        f"{numbered}"
    )

    client = _make_openai_client()
    resp = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return _parse_numbered_response(resp.choices[0].message.content, len(texts))


def _parse_numbered_response(text: str, expected: int) -> list[str]:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    results = []
    for line in lines:
        m = re.match(r"^\d+\.\s*(.+)$", line)
        if m:
            results.append(m.group(1))
    while len(results) < expected:
        results.append("")
    return results[:expected]
