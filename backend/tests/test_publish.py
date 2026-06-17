"""Integration test: the _maybe_publish pipeline hook (mocked upload)."""
import pytest

from models.job import Job, JobMode, JobStatus, JobStep
from core.task_manager import TaskManager
import services.pipeline as pl


async def test_maybe_publish_skipped_without_platforms():
    tm = TaskManager()
    job = Job(output_file="/x.mp4", publish_platforms=[])
    tm.create_job(job)
    await pl._maybe_publish(job, tm)
    assert job.get_step(JobStep.PUBLISH) is None


async def test_maybe_publish_success(monkeypatch):
    async def fake_pub(video, title, platforms, job_id):
        return {"success": True, "platforms": platforms}
    monkeypatch.setattr("services.publish.upload_post.publish_video", fake_pub)

    tm = TaskManager()
    job = Job(output_file="/x.mp4", publish_platforms=["tiktok", "instagram"], publish_title="t")
    tm.create_job(job)
    await pl._maybe_publish(job, tm)

    step = job.get_step(JobStep.PUBLISH)
    assert step is not None and step.status == JobStatus.COMPLETED
    assert job.publish_result == {"success": True, "platforms": ["tiktok", "instagram"]}


async def test_maybe_publish_failure_is_nonfatal(monkeypatch):
    async def boom(video, title, platforms, job_id):
        raise RuntimeError("upload-post down")
    monkeypatch.setattr("services.publish.upload_post.publish_video", boom)

    tm = TaskManager()
    job = Job(output_file="/x.mp4", publish_platforms=["tiktok"])
    tm.create_job(job)
    # must NOT raise — video is already produced
    await pl._maybe_publish(job, tm)

    step = job.get_step(JobStep.PUBLISH)
    assert step.status == JobStatus.FAILED
    assert "error" in (job.publish_result or {})
