from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from api.routes import tasks, jobs, system, media, assets
from core.config import settings
from core.task_manager import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await task_manager.start()
    yield
    await task_manager.stop()


app = FastAPI(
    title="Eidon API",
    description="AI Video Processing Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(media.router, prefix="/api/media", tags=["media"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])

# Serve output files
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=settings.OUTPUT_DIR), name="outputs")
