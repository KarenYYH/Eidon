import asyncio
from pathlib import Path
from loguru import logger

from core.config import settings

_subtitles_filter_available: bool | None = None


async def _has_subtitles_filter() -> bool:
    """Check once whether this ffmpeg build supports the subtitles filter (needs libass)."""
    global _subtitles_filter_available
    if _subtitles_filter_available is not None:
        return _subtitles_filter_available
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-filters",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    _subtitles_filter_available = b" subtitles " in stdout
    if not _subtitles_filter_available:
        logger.warning("ffmpeg has no 'subtitles' filter (libass not enabled); subtitles will not be burned in")
    return _subtitles_filter_available


def _escape_subtitle_path(srt_path: str) -> str:
    """Escape an SRT path for use inside the subtitles=... filter argument.

    The colon after a Windows drive letter (C:) must be escaped because ':' is
    the filter option separator; backslashes are normalised to forward slashes.
    POSIX paths need no colon escaping.
    """
    p = srt_path.replace("\\", "/")
    # Escape a leading drive-letter colon only (e.g. C: -> C\:)
    if len(p) > 1 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p


def _hex_to_ass_colour(hex_colour: str) -> str:
    """Convert #RRGGBB to libass &HBBGGRR& (ASS uses BGR, no alpha here)."""
    h = (hex_colour or "").lstrip("#")
    if len(h) != 6:
        return "&HFFFFFF&"
    rr, gg, bb = h[0:2], h[2:4], h[4:6]
    return f"&H{bb}{gg}{rr}&".upper()


def _build_force_style(style: dict | None) -> str:
    """Build a libass force_style string from a per-job subtitle style dict.

    style keys (all optional): font, position(top|center|bottom), font_size,
    color, stroke_color, stroke_width. Missing keys fall back to settings.
    """
    style = style or {}
    font = style.get("font") or settings.SUBTITLE_FONT
    position = style.get("position") or settings.SUBTITLE_POSITION
    font_size = style.get("font_size") or settings.SUBTITLE_FONT_SIZE
    color = style.get("color") or settings.SUBTITLE_COLOR
    stroke_color = style.get("stroke_color") or settings.SUBTITLE_STROKE_COLOR
    stroke_width = style.get("stroke_width")
    if stroke_width is None:
        stroke_width = settings.SUBTITLE_STROKE_WIDTH

    # ASS Alignment (numpad): 2=bottom-centre, 5=middle-centre, 8=top-centre
    alignment = {"top": 8, "center": 5, "bottom": 2}.get(position, 2)

    parts = []
    if font:
        parts.append(f"FontName={font}")
    parts.append(f"FontSize={font_size}")
    parts.append(f"PrimaryColour={_hex_to_ass_colour(color)}")
    parts.append(f"OutlineColour={_hex_to_ass_colour(stroke_color)}")
    parts.append(f"Outline={stroke_width}")
    parts.append(f"Alignment={alignment}")
    return ",".join(parts)


async def mix_video(
    video_path: str,
    audio_path: str,
    srt_path: str,
    job_id: str,
    subtitle_style: dict | None = None,
) -> str:
    out_dir = Path(settings.OUTPUT_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output = str(out_dir / "output.mp4")

    burn_subs = bool(srt_path) and await _has_subtitles_filter()
    if burn_subs:
        srt_escaped = _escape_subtitle_path(srt_path)
        # force_style controls font/size/colour/outline/position; libass otherwise
        # defaults to PingFang (unreadable on macOS) → tofu boxes for Chinese.
        vf = f"subtitles='{srt_escaped}':force_style='{_build_force_style(subtitle_style)}'"
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path, "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", vf,
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            output,
        ]
        logger.info(f"[{job_id}] Mixing video with burned-in subtitles")
        ok = await _run(cmd)
        if ok:
            logger.info(f"[{job_id}] Output: {output}")
            return output
        logger.warning(f"[{job_id}] Subtitle burn failed, falling back to no-subtitle mux")

    # No subtitle burn (filter unavailable, no SRT, or burn failed)
    cmd2 = [
        "ffmpeg", "-y",
        "-i", video_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        output,
    ]
    if not await _run(cmd2):
        raise RuntimeError("FFmpeg mix_video failed")

    logger.info(f"[{job_id}] Output: {output}")
    return output


async def mix_assembled(assembled_path: str, audio_path: str, job_id: str) -> str:
    """Merge the assembled (silent) video with the TTS audio track."""
    out_dir = Path(settings.OUTPUT_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output = str(out_dir / "output.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", assembled_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        output,
    ]
    ok = await _run(cmd)
    if not ok:
        raise RuntimeError("FFmpeg mix_assembled failed")
    return output


async def mix_with_bgm(video_path: str, bgm_path: str, job_id: str, volume_db: float | None = None) -> str:
    """Mix BGM into an already-rendered video. BGM ducked to `volume_db` (dB)."""
    out_dir = Path(settings.OUTPUT_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output = str(out_dir / "output_bgm.mp4")
    vol = settings.BGM_VOLUME_DB if volume_db is None else volume_db
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={vol}dB,afade=t=in:d=2,afade=t=out:st=9999:d=2[bgm];"
        "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        output,
    ]
    ok = await _run(cmd)
    if not ok:
        logger.warning(f"[{job_id}] BGM mix failed, returning original")
        return video_path
    return output


async def _run(cmd: list[str]) -> bool:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(f"FFmpeg error: {stderr.decode()[-500:]}")
        return False
    return True
