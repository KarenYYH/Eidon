from enum import Enum
from typing import Optional, Any, List
from pydantic import BaseModel
import uuid
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStep(str, Enum):
    DOWNLOAD = "download"
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"
    TTS = "tts"
    SYNTHESIZE = "synthesize"
    SCRIPT = "script"
    REWRITE = "rewrite"
    ASSEMBLE = "assemble"
    LIPSYNC = "lipsync"
    DISPATCH = "dispatch"
    PUBLISH = "publish"


class JobMode(str, Enum):
    TRANSLATE = "translate"            # download → transcribe → translate → tts → mix
    CREATE = "create"                 # topic → script → tts → assemble → mix
    DIGITAL_HUMAN = "digital_human"   # text/audio → tts → lipsync (talking-head avatar)
    REWRITE = "rewrite"               # url → transcribe → rewrite×N → spawn N digital_human children


class StepStatus(BaseModel):
    step: JobStep
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class Job(BaseModel):
    id: str = ""
    title: str = ""
    mode: JobMode = JobMode.TRANSLATE

    # Translate mode
    source_url: str = ""
    source_file: Optional[str] = None

    # Create mode
    topic: str = ""
    duration_sec: int = 60
    script_language: str = "zh"
    scenes: List[dict] = []

    # Digital-human mode
    text: str = ""                          # narration script (skipped if audio given directly)
    avatar_video: Optional[str] = None      # reference face video for HeyGem lip-sync

    # Voice cloning (CosyVoice zero-shot) — used by any mode when tts_provider == cosyvoice
    prompt_audio: Optional[str] = None      # reference voice sample (wav)
    prompt_text: Optional[str] = None       # transcript of the reference sample

    # Rewrite (batch) mode — url → transcribe → rewrite into N scripts → N digital-human children
    script_count: int = 3                   # how many rewritten scripts to produce
    rewrite_style: str = ""                 # free-text style/angle instruction for the rewrite
    scripts: List[str] = []                 # the N rewritten narration scripts
    parent_id: Optional[str] = None         # set on child jobs, points to the rewrite parent
    child_ids: List[str] = []               # set on the parent, lists spawned child job ids

    # Common
    status: JobStatus = JobStatus.PENDING
    steps: List[StepStatus] = []
    progress: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    target_language: str = "zh"
    tts_provider: str = "edge"
    voice: str = ""
    bgm_enabled: bool = False
    bgm_volume_db: Optional[float] = None    # None = use settings default

    # Video composition (create mode): aspect ratio, concat order, clip length, transitions
    video_aspect: str = "9:16"               # 9:16 | 16:9 | 1:1
    video_concat_mode: str = "sequential"    # sequential | random
    clip_duration: Optional[float] = None    # per-scene clip seconds (None = scene duration)
    transition: str = "none"                 # none | fade | slide

    # Subtitle style (None fields fall back to settings defaults)
    subtitle_position: Optional[str] = None  # top | center | bottom
    subtitle_font_size: Optional[int] = None
    subtitle_color: Optional[str] = None
    subtitle_stroke_color: Optional[str] = None
    subtitle_stroke_width: Optional[float] = None

    # Publishing
    publish_platforms: List[str] = []        # e.g. ["tiktok", "instagram"]; empty = no publish
    publish_title: str = ""
    publish_result: Optional[dict] = None

    # Results
    subtitle_file: Optional[str] = None
    audio_file: Optional[str] = None
    output_file: Optional[str] = None
    error: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    def get_step(self, step: JobStep) -> Optional[StepStatus]:
        for s in self.steps:
            if s.step == step:
                return s
        return None
