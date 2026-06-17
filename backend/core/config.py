from pydantic_settings import BaseSettings
from typing import List
import os

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    APP_NAME: str = "Eidon"
    DEBUG: bool = False

    # Dirs
    BASE_DIR: str = _BASE
    OUTPUT_DIR: str = os.path.join(_BASE, "outputs")
    TEMP_DIR: str = os.path.join(_BASE, "temp")
    MEDIA_DIR: str = os.path.join(_BASE, "media")
    BGM_DIR: str = os.path.join(_BASE, "bgm")
    VOICES_DIR: str = os.path.join(_BASE, "voices")    # CosyVoice clone reference samples
    AVATARS_DIR: str = os.path.join(_BASE, "avatars")  # HeyGem face reference videos

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # LLM — unified OpenAI-compatible interface
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""          # empty = official OpenAI endpoint
    LLM_MODEL: str = "gpt-4o-mini"  # any model name the provider supports

    # Whisper
    WHISPER_MODEL: str = "base"     # tiny, base, small, medium, large

    # TTS
    TTS_PROVIDER: str = "edge"      # edge | cosyvoice
    EDGE_TTS_VOICE: str = "zh-CN-XiaoxiaoNeural"

    # Subtitle burn-in font (must be a fontconfig-resolvable family name).
    # macOS default PingFang lives in a path libass can't read; "Heiti SC",
    # "Songti SC" and "Arial Unicode MS" all work and cover CJK glyphs.
    SUBTITLE_FONT: str = "Heiti SC"
    # Default subtitle style (overridable per-job). position: top|center|bottom
    SUBTITLE_POSITION: str = "bottom"
    SUBTITLE_FONT_SIZE: int = 24
    SUBTITLE_COLOR: str = "#FFFFFF"          # primary text colour (#RRGGBB)
    SUBTITLE_STROKE_COLOR: str = "#000000"   # outline colour
    SUBTITLE_STROKE_WIDTH: float = 1.5

    # Default BGM mixing volume in dB (negative = quieter than narration)
    BGM_VOLUME_DB: float = -18.0

    # Online stock-video material providers (free tiers). Empty key = disabled.
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""
    STOCK_PROVIDER: str = "pexels"           # pexels | pixabay
    STOCK_ENABLED: bool = False              # auto-download clips when local library misses

    # Multi-platform publishing via upload-post.com (optional).
    UPLOAD_POST_API_KEY: str = ""
    UPLOAD_POST_HOST: str = "https://api.upload-post.com"

    # CosyVoice — zero-shot voice cloning inference server (FunAudioLLM/CosyVoice
    # runtime/python/fastapi). Streams raw PCM int16; CosyVoice2 is 24 kHz mono.
    COSYVOICE_HOST: str = "http://localhost:50000"
    COSYVOICE_SAMPLE_RATE: int = 24000

    # HeyGem — digital-human / lip-sync service (Duix.Heygem face2face).
    # Async: submit a job then poll until the synthesized video is ready.
    HEYGEM_HOST: str = "http://localhost:8383"
    HEYGEM_POLL_INTERVAL: float = 3.0     # seconds between status polls
    HEYGEM_TIMEOUT: float = 1800.0        # max seconds to wait for a result

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

for _d in (settings.OUTPUT_DIR, settings.TEMP_DIR, settings.MEDIA_DIR,
           settings.BGM_DIR, settings.VOICES_DIR, settings.AVATARS_DIR):
    os.makedirs(_d, exist_ok=True)
