import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime
from loguru import logger

from models.job import Job, JobStatus, JobStep, StepStatus


class TaskManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._subscribers: Dict[str, list] = {}  # job_id -> list of queues
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Task manager started")

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()

    def create_job(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    async def submit(self, job: Job):
        self._jobs[job.id] = job
        await self._queue.put(job.id)
        logger.info(f"Job {job.id} submitted")

    async def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return False
        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.utcnow()
        await self._broadcast(job)
        return True

    def subscribe(self, job_id: str, queue: asyncio.Queue):
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(queue)
            except ValueError:
                pass

    async def _broadcast(self, job: Job):
        queues = self._subscribers.get(job.id, [])
        for q in queues:
            try:
                q.put_nowait(job.model_dump(mode="json"))
            except asyncio.QueueFull:
                pass

    async def update_step(self, job: Job, step: JobStep, status: JobStatus,
                          progress: float = 0.0, message: str = "", error: str = None):
        step_obj = job.get_step(step)
        if not step_obj:
            step_obj = StepStatus(step=step)
            job.steps.append(step_obj)

        step_obj.status = status
        step_obj.progress = progress
        step_obj.message = message
        if error:
            step_obj.error = error
        if status == JobStatus.RUNNING and not step_obj.started_at:
            step_obj.started_at = datetime.utcnow()
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            step_obj.completed_at = datetime.utcnow()

        # Overall progress: average of step progresses
        completed_steps = [s for s in job.steps if s.status == JobStatus.COMPLETED]
        job.progress = (len(completed_steps) / max(len(job.steps), 1)) * 100
        job.updated_at = datetime.utcnow()
        await self._broadcast(job)

    async def _worker(self):
        from services.pipeline import run_pipeline
        while True:
            try:
                job_id = await self._queue.get()
                job = self._jobs.get(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    continue
                job.status = JobStatus.RUNNING
                job.updated_at = datetime.utcnow()
                await self._broadcast(job)
                try:
                    await run_pipeline(job, self)
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
                except Exception as e:
                    logger.exception(f"Job {job_id} failed: {e}")
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                finally:
                    job.updated_at = datetime.utcnow()
                    await self._broadcast(job)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Worker error: {e}")


task_manager = TaskManager()
