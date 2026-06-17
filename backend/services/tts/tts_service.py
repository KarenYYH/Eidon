import asyncio
import re
from pathlib import Path
from loguru import logger

from core.config import settings


async def synthesize_tts_from_text(
    full_text: str,
    scenes: list[dict],
    job_id: str,
    provider: str = "edge",
    voice: str = "",
    prompt_audio: str = "",
    prompt_text: str = "",
) -> str:
    """For CREATE mode: synthesize TTS from scene narrations sequentially."""
    from core.config import settings as _s
    import tempfile, os

    out_dir = Path(_s.TEMP_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / "dubbed_audio.wav")

    # Build pseudo-segments from scenes with cumulative timestamps
    segments = []
    cursor = 0.0
    for scene in scenes:
        dur = float(scene.get("duration", 5))
        segments.append({
            "start": cursor,
            "end": cursor + dur,
            "text": scene.get("narration", ""),
        })
        cursor += dur

    logger.info(f"[{job_id}] TTS-from-text ({provider}): {len(segments)} scenes")

    if provider == "cosyvoice":
        return await _tts_cosyvoice(segments, out_path, prompt_audio, prompt_text, job_id)
    else:
        return await _tts_edge(segments, out_path, voice or _s.EDGE_TTS_VOICE, job_id)


async def synthesize_tts(
    srt_path: str,
    job_id: str,
    provider: str = "edge",
    voice: str = "",
    prompt_audio: str = "",
    prompt_text: str = "",
) -> str:
    out_dir = Path(srt_path).parent
    out_path = str(out_dir / "dubbed_audio.wav")

    segments = _parse_srt_for_tts(srt_path)
    if not segments:
        raise ValueError("No TTS segments found")

    logger.info(f"[{job_id}] TTS ({provider}): {len(segments)} segments")

    if provider == "cosyvoice":
        return await _tts_cosyvoice(segments, out_path, prompt_audio, prompt_text, job_id)
    else:
        return await _tts_edge(segments, out_path, voice or settings.EDGE_TTS_VOICE, job_id)


def _parse_srt_for_tts(srt_path: str) -> list[dict]:
    text = Path(srt_path).read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", text.strip())
    segments = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            timecode = lines[1]
            start_str, end_str = timecode.split(" --> ")
            content = " ".join(lines[2:])
            segments.append({
                "start": _srt_time_to_seconds(start_str.strip()),
                "end": _srt_time_to_seconds(end_str.strip()),
                "text": content,
            })
        except (ValueError, IndexError):
            continue
    return segments


def _srt_time_to_seconds(t: str) -> float:
    t = t.replace(",", ".")
    parts = t.split(":")
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


async def _tts_edge(segments: list[dict], out_path: str, voice: str, job_id: str) -> str:
    import edge_tts
    from pydub import AudioSegment
    import io

    out_dir = Path(out_path).parent
    clips = []

    for i, seg in enumerate(segments):
        tmp = str(out_dir / f"_tts_seg_{i}.mp3")
        communicate = edge_tts.Communicate(seg["text"], voice)
        await communicate.save(tmp)
        clips.append((seg["start"], seg["end"], tmp))

    # Merge clips at correct timestamps using pydub
    if not clips:
        raise RuntimeError("No TTS clips generated")

    total_duration = int(clips[-1][1] * 1000) + 500
    combined = AudioSegment.silent(duration=total_duration)

    for start, end, clip_path in clips:
        clip = AudioSegment.from_mp3(clip_path)
        # Speed-adjust if clip is longer than slot
        slot_ms = int((end - start) * 1000)
        if len(clip) > slot_ms and slot_ms > 0:
            ratio = len(clip) / slot_ms
            clip = clip.speedup(playback_speed=min(ratio, 2.0))
        combined = combined.overlay(clip, position=int(start * 1000))

    combined.export(out_path, format="wav")
    logger.info(f"[{job_id}] EdgeTTS audio: {out_path}")
    return out_path


async def _tts_cosyvoice(
    segments: list[dict],
    out_path: str,
    prompt_audio: str,
    prompt_text: str,
    job_id: str,
) -> str:
    """Zero-shot voice cloning via the FunAudioLLM/CosyVoice FastAPI runtime.

    Calls POST /inference_zero_shot with form fields `tts_text` + `prompt_text`
    and the reference sample as file `prompt_wav`. The server streams raw PCM
    int16 mono at COSYVOICE_SAMPLE_RATE, which we wrap into a WAV per segment
    and overlay at the SRT timestamps.
    """
    import httpx
    from pydub import AudioSegment

    if not prompt_audio or not Path(prompt_audio).exists():
        raise RuntimeError(
            "CosyVoice 零样本克隆需要参考音频 (prompt_audio)，但未提供或文件不存在"
        )
    if not prompt_text:
        raise RuntimeError("CosyVoice 零样本克隆需要参考音频的文字稿 (prompt_text)")

    out_dir = Path(out_path).parent
    clips: list[tuple[float, float, str]] = []
    prompt_bytes = Path(prompt_audio).read_bytes()
    prompt_name = Path(prompt_audio).name

    async with httpx.AsyncClient(timeout=120) as client:
        for i, seg in enumerate(segments):
            if not seg["text"].strip():
                continue
            resp = await client.post(
                f"{settings.COSYVOICE_HOST}/inference_zero_shot",
                data={"tts_text": seg["text"], "prompt_text": prompt_text},
                files={"prompt_wav": (prompt_name, prompt_bytes, "audio/wav")},
            )
            resp.raise_for_status()
            tmp = str(out_dir / f"_cosyvoice_{i}.wav")
            _pcm_to_wav(resp.content, tmp, settings.COSYVOICE_SAMPLE_RATE)
            clips.append((seg["start"], seg["end"], tmp))

    if not clips:
        raise RuntimeError("No TTS clips generated")

    total_duration = int(clips[-1][1] * 1000) + 500
    combined = AudioSegment.silent(duration=total_duration)
    for start, end, clip_path in clips:
        clip = AudioSegment.from_wav(clip_path)
        slot_ms = int((end - start) * 1000)
        if len(clip) > slot_ms and slot_ms > 0:
            ratio = len(clip) / slot_ms
            clip = clip.speedup(playback_speed=min(ratio, 2.0))
        combined = combined.overlay(clip, position=int(start * 1000))

    combined.export(out_path, format="wav")
    logger.info(f"[{job_id}] CosyVoice (zero-shot) audio: {out_path}")
    return out_path


def _pcm_to_wav(pcm_bytes: bytes, out_path: str, sample_rate: int, channels: int = 1):
    """Wrap raw little-endian PCM int16 bytes in a WAV container."""
    import wave
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
