from loguru import logger

from models.job import Job, JobStatus, JobStep, JobMode, StepStatus
from core.task_manager import TaskManager


async def run_pipeline(job: Job, tm: TaskManager):
    if job.mode == JobMode.CREATE:
        await _run_create_pipeline(job, tm)
    elif job.mode == JobMode.DIGITAL_HUMAN:
        await _run_digital_human_pipeline(job, tm)
    elif job.mode == JobMode.REWRITE:
        await _run_rewrite_pipeline(job, tm)
    else:
        await _run_translate_pipeline(job, tm)


def _subtitle_style(job: Job) -> dict:
    """Per-job subtitle style overrides; None fields fall back to settings."""
    return {
        "position": job.subtitle_position,
        "font_size": job.subtitle_font_size,
        "color": job.subtitle_color,
        "stroke_color": job.subtitle_stroke_color,
        "stroke_width": job.subtitle_stroke_width,
    }


async def _maybe_publish(job: Job, tm: TaskManager):
    """If the job requests publishing, upload the final video. Appends a PUBLISH
    step; a publish failure does NOT fail the whole job (video is already made)."""
    if not job.publish_platforms or not job.output_file:
        return
    from services.publish.upload_post import publish_video
    job.steps.append(StepStatus(step=JobStep.PUBLISH))
    await tm.update_step(job, JobStep.PUBLISH, JobStatus.RUNNING, 0,
                         f"Publishing to {', '.join(job.publish_platforms)}…")
    try:
        result = await publish_video(
            job.output_file, job.publish_title or job.title,
            job.publish_platforms, job.id,
        )
        job.publish_result = result
        await tm.update_step(job, JobStep.PUBLISH, JobStatus.COMPLETED, 100, "Published")
    except Exception as e:
        # Non-fatal: keep the rendered video, just mark publish failed
        job.publish_result = {"error": str(e)}
        await tm.update_step(job, JobStep.PUBLISH, JobStatus.FAILED, 0, str(e), str(e))


# ── Translate pipeline ────────────────────────────────────────────────────────

async def _run_translate_pipeline(job: Job, tm: TaskManager):
    from services.downloader.downloader import download_video
    from services.transcriber.whisper_stt import transcribe
    from services.translator.translator import translate_subtitles
    from services.tts.tts_service import synthesize_tts
    from services.synthesizer.ffmpeg_mix import mix_video, mix_with_bgm
    from core.config import settings

    steps = [JobStep.DOWNLOAD, JobStep.TRANSCRIBE, JobStep.TRANSLATE, JobStep.TTS, JobStep.SYNTHESIZE]
    for s in steps:
        job.steps.append(StepStatus(step=s))

    await tm.update_step(job, JobStep.DOWNLOAD, JobStatus.RUNNING, 0, "Downloading video…")
    try:
        video_path = await download_video(job.source_url or job.source_file, job.id)
        job.source_file = video_path
        await tm.update_step(job, JobStep.DOWNLOAD, JobStatus.COMPLETED, 100, "Download complete")
    except Exception as e:
        await tm.update_step(job, JobStep.DOWNLOAD, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.TRANSCRIBE, JobStatus.RUNNING, 0, "Transcribing audio…")
    try:
        subtitle_path = await transcribe(video_path, job.id, settings.WHISPER_MODEL)
        job.subtitle_file = subtitle_path
        await tm.update_step(job, JobStep.TRANSCRIBE, JobStatus.COMPLETED, 100, "Transcription complete")
    except Exception as e:
        await tm.update_step(job, JobStep.TRANSCRIBE, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.TRANSLATE, JobStatus.RUNNING, 0, f"Translating to {job.target_language}…")
    try:
        translated_path = await translate_subtitles(subtitle_path, job.target_language, job.id)
        job.subtitle_file = translated_path
        await tm.update_step(job, JobStep.TRANSLATE, JobStatus.COMPLETED, 100, "Translation complete")
    except Exception as e:
        await tm.update_step(job, JobStep.TRANSLATE, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.TTS, JobStatus.RUNNING, 0, "Synthesizing speech…")
    try:
        audio_path = await synthesize_tts(
            translated_path, job.id, job.tts_provider, job.voice,
            job.prompt_audio or "", job.prompt_text or "",
        )
        job.audio_file = audio_path
        await tm.update_step(job, JobStep.TTS, JobStatus.COMPLETED, 100, "TTS complete")
    except Exception as e:
        await tm.update_step(job, JobStep.TTS, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.SYNTHESIZE, JobStatus.RUNNING, 0, "Mixing video…")
    try:
        output_path = await mix_video(video_path, audio_path, job.subtitle_file, job.id,
                                       subtitle_style=_subtitle_style(job))
        if job.bgm_enabled:
            from services.media.local_library import get_random_bgm
            bgm = get_random_bgm()
            if bgm:
                output_path = await mix_with_bgm(output_path, bgm, job.id, job.bgm_volume_db)
        job.output_file = output_path
        await tm.update_step(job, JobStep.SYNTHESIZE, JobStatus.COMPLETED, 100, "Video ready")
    except Exception as e:
        await tm.update_step(job, JobStep.SYNTHESIZE, JobStatus.FAILED, 0, str(e), str(e)); raise

    await _maybe_publish(job, tm)


# ── Create pipeline ───────────────────────────────────────────────────────────

async def _run_create_pipeline(job: Job, tm: TaskManager):
    from services.script.script_generator import generate_script
    from services.script.scene_assembler import assemble_scenes
    from services.tts.tts_service import synthesize_tts_from_text
    from services.synthesizer.ffmpeg_mix import mix_assembled, mix_with_bgm
    from core.config import settings

    steps = [JobStep.SCRIPT, JobStep.TTS, JobStep.ASSEMBLE, JobStep.SYNTHESIZE]
    for s in steps:
        job.steps.append(StepStatus(step=s))

    await tm.update_step(job, JobStep.SCRIPT, JobStatus.RUNNING, 0, "Generating script…")
    try:
        scenes = await generate_script(job.topic, job.duration_sec, job.script_language)
        job.scenes = scenes
        await tm.update_step(job, JobStep.SCRIPT, JobStatus.COMPLETED, 100, f"Script ready: {len(scenes)} scenes")
    except Exception as e:
        await tm.update_step(job, JobStep.SCRIPT, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.TTS, JobStatus.RUNNING, 0, "Synthesizing narration…")
    try:
        full_narration = "\n".join(s["narration"] for s in scenes)
        audio_path = await synthesize_tts_from_text(
            full_narration, job.scenes, job.id, job.tts_provider, job.voice,
            job.prompt_audio or "", job.prompt_text or "",
        )
        job.audio_file = audio_path
        await tm.update_step(job, JobStep.TTS, JobStatus.COMPLETED, 100, "Narration ready")
    except Exception as e:
        await tm.update_step(job, JobStep.TTS, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.ASSEMBLE, JobStatus.RUNNING, 0, "Assembling scenes…")
    try:
        assembled_path = await assemble_scenes(
            job.scenes, audio_path, job.id,
            aspect=job.video_aspect, concat_mode=job.video_concat_mode,
            clip_duration=job.clip_duration, transition=job.transition,
        )
        await tm.update_step(job, JobStep.ASSEMBLE, JobStatus.COMPLETED, 100, "Scenes assembled")
    except Exception as e:
        await tm.update_step(job, JobStep.ASSEMBLE, JobStatus.FAILED, 0, str(e), str(e)); raise

    await tm.update_step(job, JobStep.SYNTHESIZE, JobStatus.RUNNING, 0, "Mixing final video…")
    try:
        output_path = await mix_assembled(assembled_path, audio_path, job.id)
        if job.bgm_enabled:
            from services.media.local_library import get_random_bgm
            bgm = get_random_bgm()
            if bgm:
                output_path = await mix_with_bgm(output_path, bgm, job.id, job.bgm_volume_db)
        job.output_file = output_path
        await tm.update_step(job, JobStep.SYNTHESIZE, JobStatus.COMPLETED, 100, "Video ready")
    except Exception as e:
        await tm.update_step(job, JobStep.SYNTHESIZE, JobStatus.FAILED, 0, str(e), str(e)); raise

    await _maybe_publish(job, tm)


# ── Digital-human pipeline ──────────────────────────────────────────────────────

async def _run_digital_human_pipeline(job: Job, tm: TaskManager):
    """text → TTS (edge or cosyvoice clone) → HeyGem lip-sync.

    If `job.audio_file` is already set (caller supplied audio directly), the TTS
    step is skipped and that audio drives the avatar.
    """
    from services.tts.tts_service import synthesize_tts_from_text
    from services.lipsync.heygem import generate_digital_human

    steps = [JobStep.TTS, JobStep.LIPSYNC]
    for s in steps:
        job.steps.append(StepStatus(step=s))

    # 1) Narration audio
    if job.audio_file:
        await tm.update_step(job, JobStep.TTS, JobStatus.COMPLETED, 100, "Using supplied audio")
        audio_path = job.audio_file
    else:
        await tm.update_step(job, JobStep.TTS, JobStatus.RUNNING, 0, "Synthesizing narration…")
        try:
            if not job.text.strip():
                raise ValueError("数字人模式需要文稿 (text) 或音频文件")
            scenes = [{"narration": job.text, "duration": 0}]
            audio_path = await synthesize_tts_from_text(
                job.text, scenes, job.id, job.tts_provider, job.voice,
                job.prompt_audio or "", job.prompt_text or "",
            )
            job.audio_file = audio_path
            await tm.update_step(job, JobStep.TTS, JobStatus.COMPLETED, 100, "Narration ready")
        except Exception as e:
            await tm.update_step(job, JobStep.TTS, JobStatus.FAILED, 0, str(e), str(e)); raise

    # 2) Lip-sync against the avatar face video
    await tm.update_step(job, JobStep.LIPSYNC, JobStatus.RUNNING, 0, "Generating digital human…")
    try:
        output_path = await generate_digital_human(audio_path, job.avatar_video, job.id)
        job.output_file = output_path
        await tm.update_step(job, JobStep.LIPSYNC, JobStatus.COMPLETED, 100, "Digital human ready")
    except Exception as e:
        await tm.update_step(job, JobStep.LIPSYNC, JobStatus.FAILED, 0, str(e), str(e)); raise

    await _maybe_publish(job, tm)


# ── Rewrite (batch) pipeline ────────────────────────────────────────────────────

def _srt_to_plain_text(srt_path: str) -> str:
    """Extract just the spoken text from an SRT file (drop indices/timecodes)."""
    import re
    from pathlib import Path
    text = Path(srt_path).read_text(encoding="utf-8")
    lines = []
    for block in re.split(r"\n\n+", text.strip()):
        rows = block.strip().splitlines()
        if len(rows) >= 3:
            lines.append(" ".join(rows[2:]))
        elif len(rows) == 1 and not rows[0].strip().isdigit():
            lines.append(rows[0])
    return " ".join(lines).strip()


async def _run_rewrite_pipeline(job: Job, tm: TaskManager):
    """url/file → download → transcribe → rewrite into N scripts → spawn N
    digital-human child jobs (one per script). The parent completes once the
    children are queued; each child runs the digital_human pipeline on its own.
    """
    from services.downloader.downloader import download_video
    from services.transcriber.whisper_stt import transcribe
    from services.script.rewriter import rewrite_scripts
    from core.config import settings

    steps = [JobStep.DOWNLOAD, JobStep.TRANSCRIBE, JobStep.REWRITE, JobStep.DISPATCH]
    for s in steps:
        job.steps.append(StepStatus(step=s))

    # 1) Download
    await tm.update_step(job, JobStep.DOWNLOAD, JobStatus.RUNNING, 0, "Downloading video…")
    try:
        video_path = await download_video(job.source_url or job.source_file, job.id)
        job.source_file = video_path
        await tm.update_step(job, JobStep.DOWNLOAD, JobStatus.COMPLETED, 100, "Download complete")
    except Exception as e:
        await tm.update_step(job, JobStep.DOWNLOAD, JobStatus.FAILED, 0, str(e), str(e)); raise

    # 2) Transcribe original spoken script
    await tm.update_step(job, JobStep.TRANSCRIBE, JobStatus.RUNNING, 0, "Transcribing audio…")
    try:
        subtitle_path = await transcribe(video_path, job.id, settings.WHISPER_MODEL)
        job.subtitle_file = subtitle_path
        original_text = _srt_to_plain_text(subtitle_path)
        await tm.update_step(job, JobStep.TRANSCRIBE, JobStatus.COMPLETED, 100, "Transcription complete")
    except Exception as e:
        await tm.update_step(job, JobStep.TRANSCRIBE, JobStatus.FAILED, 0, str(e), str(e)); raise

    # 3) Rewrite into N fresh scripts
    await tm.update_step(job, JobStep.REWRITE, JobStatus.RUNNING, 0,
                         f"Rewriting into {job.script_count} scripts…")
    try:
        scripts = await rewrite_scripts(
            original_text, job.script_count, job.rewrite_style, job.script_language,
        )
        job.scripts = scripts
        await tm.update_step(job, JobStep.REWRITE, JobStatus.COMPLETED, 100,
                             f"{len(scripts)} scripts ready")
    except Exception as e:
        await tm.update_step(job, JobStep.REWRITE, JobStatus.FAILED, 0, str(e), str(e)); raise

    # 4) Spawn one digital-human child job per script
    await tm.update_step(job, JobStep.DISPATCH, JobStatus.RUNNING, 0, "Dispatching digital-human jobs…")
    try:
        child_ids = []
        for i, script in enumerate(job.scripts):
            child = Job(
                title=f"{job.title or 'Rewrite'} #{i + 1}",
                mode=JobMode.DIGITAL_HUMAN,
                text=script,
                avatar_video=job.avatar_video,
                tts_provider=job.tts_provider,
                voice=job.voice,
                prompt_audio=job.prompt_audio,
                prompt_text=job.prompt_text,
                script_language=job.script_language,
                parent_id=job.id,
            )
            await tm.submit(child)
            child_ids.append(child.id)
        job.child_ids = child_ids
        await tm.update_step(job, JobStep.DISPATCH, JobStatus.COMPLETED, 100,
                             f"Dispatched {len(child_ids)} digital-human jobs")
    except Exception as e:
        await tm.update_step(job, JobStep.DISPATCH, JobStatus.FAILED, 0, str(e), str(e)); raise
