"""Unit tests for the Job model and TaskManager state machine."""
import asyncio

import pytest

from models.job import Job, JobMode, JobStatus, JobStep, StepStatus
from core.task_manager import TaskManager


class TestJobModel:
    def test_auto_id_and_timestamps(self):
        j = Job(title="x")
        assert j.id and len(j.id) == 36
        assert j.created_at is not None and j.updated_at is not None

    def test_get_step(self):
        j = Job(steps=[StepStatus(step=JobStep.DOWNLOAD), StepStatus(step=JobStep.TTS)])
        assert j.get_step(JobStep.TTS).step == JobStep.TTS
        assert j.get_step(JobStep.TRANSLATE) is None

    def test_defaults(self):
        j = Job()
        assert j.mode == JobMode.TRANSLATE
        assert j.status == JobStatus.PENDING
        assert j.target_language == "zh"
        assert j.bgm_enabled is False


class TestTaskManager:
    def test_create_and_get(self):
        tm = TaskManager()
        j = Job(title="a")
        tm.create_job(j)
        assert tm.get_job(j.id) is j
        assert tm.get_job("nope") is None

    def test_get_all_sorted_newest_first(self):
        tm = TaskManager()
        import datetime
        j1 = Job(title="old"); j1.created_at = datetime.datetime(2020, 1, 1)
        j2 = Job(title="new"); j2.created_at = datetime.datetime(2025, 1, 1)
        tm.create_job(j1); tm.create_job(j2)
        assert [j.title for j in tm.get_all_jobs()] == ["new", "old"]

    async def test_update_step_progress(self):
        tm = TaskManager()
        j = Job(steps=[StepStatus(step=s) for s in (JobStep.DOWNLOAD, JobStep.TTS)])
        tm.create_job(j)
        await tm.update_step(j, JobStep.DOWNLOAD, JobStatus.COMPLETED, 100, "done")
        assert j.get_step(JobStep.DOWNLOAD).status == JobStatus.COMPLETED
        assert j.progress == 50.0  # 1 of 2 steps complete
        await tm.update_step(j, JobStep.TTS, JobStatus.COMPLETED, 100, "done")
        assert j.progress == 100.0

    async def test_update_step_sets_timestamps(self):
        tm = TaskManager()
        j = Job(steps=[StepStatus(step=JobStep.DOWNLOAD)])
        await tm.update_step(j, JobStep.DOWNLOAD, JobStatus.RUNNING, 0, "go")
        assert j.get_step(JobStep.DOWNLOAD).started_at is not None
        await tm.update_step(j, JobStep.DOWNLOAD, JobStatus.FAILED, 0, "boom", "boom")
        step = j.get_step(JobStep.DOWNLOAD)
        assert step.completed_at is not None
        assert step.error == "boom"

    async def test_subscribe_broadcast_unsubscribe(self):
        tm = TaskManager()
        j = Job(steps=[StepStatus(step=JobStep.DOWNLOAD)])
        tm.create_job(j)
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        tm.subscribe(j.id, q)
        await tm.update_step(j, JobStep.DOWNLOAD, JobStatus.RUNNING, 0, "go")
        msg = q.get_nowait()
        assert msg["id"] == j.id
        # unsubscribe must not raise (regression: was .discard on a list)
        tm.unsubscribe(j.id, q)
        tm.unsubscribe(j.id, q)  # idempotent

    async def test_cancel_pending_job(self):
        tm = TaskManager()
        j = Job()
        tm.create_job(j)
        assert await tm.cancel_job(j.id) is True
        assert j.status == JobStatus.CANCELLED
        # cannot cancel an already-completed job
        j.status = JobStatus.COMPLETED
        assert await tm.cancel_job(j.id) is False

    async def test_cancel_unknown_job(self):
        tm = TaskManager()
        assert await tm.cancel_job("missing") is False
