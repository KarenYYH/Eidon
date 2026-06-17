import asyncio
import os
import random
from pathlib import Path
from loguru import logger

from core.config import settings
from services.media.local_library import search_clips, VIDEO_EXTS, IMAGE_EXTS

ASPECT_RESOLUTIONS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


def _resolution(aspect: str) -> tuple[int, int]:
    return ASPECT_RESOLUTIONS.get(aspect, ASPECT_RESOLUTIONS["9:16"])


async def assemble_scenes(
    scenes: list[dict],
    audio_path: str,
    job_id: str,
    aspect: str = "9:16",
    concat_mode: str = "sequential",
    clip_duration: float | None = None,
    transition: str = "none",
) -> str:
    """
    Build a video from scenes by matching local clips to each scene's visual_keywords,
    then concatenating with FFmpeg. audio_path is the TTS-generated WAV.
    Returns path to the assembled video (no audio yet — audio mixed in pipeline).
    """
    out_dir = Path(settings.TEMP_DIR) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    concat_list = out_dir / "concat.txt"
    output = str(out_dir / "assembled.mp4")
    width, height = _resolution(aspect)

    clip_segments: list[str] = []
    for i, scene in enumerate(scenes):
        duration = float(clip_duration) if clip_duration else float(scene.get("duration", 5))
        keywords = scene.get("visual_keywords", [])
        matches = search_clips(keywords, count=1)
        clip_path = matches[0] if matches else None

        # No local match → try downloading a stock clip (if enabled)
        if not clip_path:
            from services.media.stock import fetch_clip
            clip_path = await fetch_clip(keywords, aspect, job_id)

        if clip_path:
            seg_path = str(out_dir / f"seg_{i}.mp4")
            await _trim_or_loop_clip(clip_path, seg_path, duration, width, height, transition)
            clip_segments.append(seg_path)
        else:
            # Fallback: black frame with scene text burned in
            seg_path = str(out_dir / f"seg_{i}.mp4")
            await _generate_text_clip(scene.get("narration", "")[:80], seg_path, duration, width, height)
            clip_segments.append(seg_path)

    if not clip_segments:
        raise RuntimeError("No video segments could be assembled")

    if concat_mode == "random":
        random.shuffle(clip_segments)

    # Write FFmpeg concat list
    lines = [f"file '{p}'\n" for p in clip_segments]
    concat_list.write_text("".join(lines))

    # Concat all segments
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast",
        "-an",  # no audio yet
        output,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {stderr.decode()}")

    logger.info(f"[{job_id}] Assembled {len(clip_segments)} scenes → {output}")
    return output


async def _trim_or_loop_clip(src: str, dst: str, duration: float, width: int, height: int, transition: str = "none"):
    suffix = Path(src).suffix.lower()
    scale_pad = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    vf = scale_pad
    # Optional fade transition at both ends of the clip
    if transition == "fade":
        fade_d = min(0.5, max(0.2, duration / 6))
        vf += f",fade=t=in:st=0:d={fade_d},fade=t=out:st={max(duration - fade_d, 0):.2f}:d={fade_d}"

    if suffix in IMAGE_EXTS:
        # Image → video
        cmd = [
            "ffmpeg", "-y", "-loop", "1",
            "-i", src,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            dst,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",   # loop if shorter than duration
            "-i", src,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an",
            dst,
        ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Clip trim failed for {src}: {stderr.decode()[:300]}")


async def _generate_text_clip(text: str, dst: str, duration: float, width: int, height: int):
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:size={width}x{height}:rate=25:duration={duration}",
        "-vf", (
            f"drawtext=text='{safe_text}':fontsize=48:fontcolor=white"
            ":x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=10:fix_bounds=true"
        ),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        dst,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        # Ultimate fallback: plain black clip
        cmd2 = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:size={width}x{height}:rate=25:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", dst,
        ]
        proc2 = await asyncio.create_subprocess_exec(*cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc2.communicate()
