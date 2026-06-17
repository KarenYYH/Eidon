from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import shutil
from pathlib import Path

from core.config import settings
from core.task_manager import task_manager
from models.job import Job, JobMode

router = APIRouter()


class CreateJobRequest(BaseModel):
    mode: str = "translate"
    # Translate mode
    source_url: Optional[str] = None
    target_language: str = "zh"
    # Create mode
    topic: Optional[str] = None
    duration_sec: int = 60
    script_language: str = "zh"
    # Digital-human mode
    text: Optional[str] = None
    avatar_video: Optional[str] = None
    # Rewrite (batch) mode
    script_count: int = 3
    rewrite_style: Optional[str] = None
    # Common
    tts_provider: str = "edge"
    voice: str = ""
    bgm_enabled: bool = False
    bgm_volume_db: Optional[float] = None
    # Voice cloning (CosyVoice zero-shot)
    prompt_audio: Optional[str] = None
    prompt_text: Optional[str] = None
    # Video composition (create mode)
    video_aspect: str = "9:16"
    video_concat_mode: str = "sequential"
    clip_duration: Optional[float] = None
    transition: str = "none"
    # Subtitle style
    subtitle_position: Optional[str] = None
    subtitle_font_size: Optional[int] = None
    subtitle_color: Optional[str] = None
    subtitle_stroke_color: Optional[str] = None
    subtitle_stroke_width: Optional[float] = None
    # Publishing
    publish_platforms: List[str] = []
    publish_title: Optional[str] = None


@router.post("")
async def create_job(req: CreateJobRequest):
    if req.mode == "create":
        if not req.topic:
            raise HTTPException(400, "topic is required for create mode")
        job = Job(
            mode=JobMode.CREATE,
            topic=req.topic,
            duration_sec=req.duration_sec,
            script_language=req.script_language,
            tts_provider=req.tts_provider,
            voice=req.voice,
            bgm_enabled=req.bgm_enabled,
            prompt_audio=req.prompt_audio,
            prompt_text=req.prompt_text,
        )
    elif req.mode == "digital_human":
        if not req.text:
            raise HTTPException(400, "text is required for digital_human mode")
        if not req.avatar_video:
            raise HTTPException(400, "avatar_video is required for digital_human mode")
        job = Job(
            mode=JobMode.DIGITAL_HUMAN,
            text=req.text,
            avatar_video=req.avatar_video,
            tts_provider=req.tts_provider,
            voice=req.voice,
            prompt_audio=req.prompt_audio,
            prompt_text=req.prompt_text,
        )
    elif req.mode == "rewrite":
        if not req.source_url:
            raise HTTPException(400, "source_url is required for rewrite mode")
        if not req.avatar_video:
            raise HTTPException(400, "avatar_video is required for rewrite mode")
        job = Job(
            mode=JobMode.REWRITE,
            source_url=req.source_url,
            script_count=req.script_count,
            rewrite_style=req.rewrite_style or "",
            script_language=req.script_language,
            avatar_video=req.avatar_video,
            tts_provider=req.tts_provider,
            voice=req.voice,
            prompt_audio=req.prompt_audio,
            prompt_text=req.prompt_text,
        )
    else:
        if not req.source_url:
            raise HTTPException(400, "source_url is required for translate mode")
        job = Job(
            mode=JobMode.TRANSLATE,
            source_url=req.source_url,
            target_language=req.target_language,
            tts_provider=req.tts_provider,
            voice=req.voice,
            bgm_enabled=req.bgm_enabled,
            prompt_audio=req.prompt_audio,
            prompt_text=req.prompt_text,
        )

    # Shared composition / subtitle-style / publishing options (apply to all modes)
    job.bgm_volume_db = req.bgm_volume_db
    job.video_aspect = req.video_aspect
    job.video_concat_mode = req.video_concat_mode
    job.clip_duration = req.clip_duration
    job.transition = req.transition
    job.subtitle_position = req.subtitle_position
    job.subtitle_font_size = req.subtitle_font_size
    job.subtitle_color = req.subtitle_color
    job.subtitle_stroke_color = req.subtitle_stroke_color
    job.subtitle_stroke_width = req.subtitle_stroke_width
    job.publish_platforms = req.publish_platforms or []
    job.publish_title = req.publish_title or ""

    await task_manager.submit(job)
    return job


@router.post("/upload")
async def create_job_from_upload(
    file: UploadFile = File(...),
    target_language: str = Form("zh"),
    tts_provider: str = Form("edge"),
    voice: str = Form(""),
    bgm_enabled: str = Form("false"),
):
    upload_dir = Path(settings.TEMP_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    job = Job(
        mode=JobMode.TRANSLATE,
        source_file=str(dest),
        target_language=target_language,
        tts_provider=tts_provider,
        voice=voice,
        bgm_enabled=bgm_enabled.lower() == "true",
    )
    await task_manager.submit(job)
    return job


@router.get("")
async def list_jobs():
    return task_manager.get_all_jobs()


@router.get("/{job_id}/children")
async def list_children(job_id: str):
    parent = task_manager.get_job(job_id)
    if not parent:
        raise HTTPException(404, "Job not found")
    return [task_manager.get_job(cid) for cid in parent.child_ids if task_manager.get_job(cid)]


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = task_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    ok = await task_manager.cancel_job(job_id)
    if not ok:
        raise HTTPException(400, "Cannot cancel job")
    return {"status": "cancelled"}
