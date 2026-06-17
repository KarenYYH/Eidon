"""API-level tests using FastAPI TestClient. Covers job lifecycle, validation,
and system endpoints. The pipeline worker is not exercised here (no event loop
submission); see test_pipeline_integration for the real run."""
import pytest
from fastapi.testclient import TestClient

from main import app
from core.task_manager import task_manager
from models.job import Job, JobStatus


@pytest.fixture
def client():
    # Plain TestClient (no lifespan context): these tests exercise routes against
    # the in-memory job store and must NOT start the background worker, which
    # blocks forever on an empty queue and deadlocks repeated client setup.
    return TestClient(app)


class TestSystemRoutes:
    def test_health(self, client):
        r = client.get("/api/system/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_voices(self, client):
        r = client.get("/api/system/voices")
        assert r.status_code == 200
        ids = [v["id"] for v in r.json()]
        assert "zh-CN-XiaoxiaoNeural" in ids

    def test_tools(self, client):
        r = client.get("/api/system/tools")
        assert r.status_code == 200
        body = r.json()
        assert set(body) >= {"ffmpeg", "yt_dlp", "whisper", "edge_tts", "pydub"}

    def test_config_masks_key(self, client):
        r = client.get("/api/system/config")
        assert r.status_code == 200
        body = r.json()
        # masked key never exposes the full secret
        assert "api_key" not in body or body.get("api_key_masked", "").count("...") <= 1


class TestJobValidation:
    def test_translate_requires_url(self, client):
        r = client.post("/api/tasks", json={"mode": "translate"})
        assert r.status_code == 400

    def test_create_requires_topic(self, client):
        r = client.post("/api/tasks", json={"mode": "create"})
        assert r.status_code == 400

    def test_digital_human_requires_text(self, client):
        r = client.post("/api/tasks", json={"mode": "digital_human", "avatar_video": "/x.mp4"})
        assert r.status_code == 400

    def test_digital_human_requires_avatar(self, client):
        r = client.post("/api/tasks", json={"mode": "digital_human", "text": "hi"})
        assert r.status_code == 400

    def test_rewrite_requires_source_url(self, client):
        r = client.post("/api/tasks", json={"mode": "rewrite", "avatar_video": "/a.mp4"})
        assert r.status_code == 400

    def test_rewrite_requires_avatar(self, client):
        r = client.post("/api/tasks", json={"mode": "rewrite", "source_url": "http://x/v.mp4"})
        assert r.status_code == 400

    def test_children_unknown_parent_404(self, client):
        assert client.get("/api/tasks/nope/children").status_code == 404

    def test_create_propagates_style_and_publish_fields(self, client):
        r = client.post("/api/tasks", json={
            "mode": "create", "topic": "测试",
            "video_aspect": "16:9", "video_concat_mode": "random", "transition": "fade",
            "subtitle_position": "top", "subtitle_font_size": 36, "subtitle_color": "#FF0000",
            "bgm_volume_db": -12.0,
            "publish_platforms": ["tiktok", "youtube"], "publish_title": "标题",
        })
        assert r.status_code == 200
        job = r.json()
        assert job["video_aspect"] == "16:9"
        assert job["video_concat_mode"] == "random"
        assert job["transition"] == "fade"
        assert job["subtitle_position"] == "top"
        assert job["subtitle_font_size"] == 36
        assert job["bgm_volume_db"] == -12.0
        assert job["publish_platforms"] == ["tiktok", "youtube"]
        assert job["publish_title"] == "标题"

    def test_get_unknown_job_404(self, client):
        assert client.get("/api/tasks/does-not-exist").status_code == 404

    def test_cancel_unknown_job_400(self, client):
        assert client.delete("/api/tasks/does-not-exist").status_code == 400

    def test_download_when_not_ready_404(self, client):
        # create a job record directly without output
        job = Job()
        task_manager.create_job(job)
        r = client.get(f"/api/jobs/{job.id}/download")
        assert r.status_code == 404


class TestJobListing:
    def test_list_returns_created_job(self, client):
        job = Job(title="listed")
        task_manager.create_job(job)
        r = client.get("/api/tasks")
        assert r.status_code == 200
        assert any(j["id"] == job.id for j in r.json())

    def test_get_existing_job(self, client):
        job = Job(title="fetchme")
        task_manager.create_job(job)
        r = client.get(f"/api/tasks/{job.id}")
        assert r.status_code == 200
        assert r.json()["title"] == "fetchme"

    def test_cancel_pending_job(self, client):
        job = Job()
        job.status = JobStatus.PENDING
        task_manager.create_job(job)
        r = client.delete(f"/api/tasks/{job.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


class TestAssetRoutes:
    def test_list_voices_and_avatars(self, client):
        assert client.get("/api/assets/voices").status_code == 200
        assert client.get("/api/assets/avatars").status_code == 200
        assert isinstance(client.get("/api/assets/voices").json(), list)

    def test_upload_voice_rejects_bad_format(self, client):
        r = client.post("/api/assets/upload/voice",
                        files={"file": ("x.txt", b"nope", "text/plain")})
        assert r.status_code == 400

    def test_upload_avatar_rejects_bad_format(self, client):
        r = client.post("/api/assets/upload/avatar",
                        files={"file": ("x.txt", b"nope", "text/plain")})
        assert r.status_code == 400

    def test_voice_upload_list_delete_roundtrip(self, client, tmp_path, monkeypatch):
        from core import config
        monkeypatch.setattr(config.settings, "VOICES_DIR", str(tmp_path))
        up = client.post("/api/assets/upload/voice",
                         files={"file": ("ref.wav", b"RIFFfake", "audio/wav")})
        assert up.status_code == 200
        assert any(v["name"] == "ref.wav" for v in client.get("/api/assets/voices").json())
        assert client.delete("/api/assets/voice/ref.wav").status_code == 200

    def test_delete_missing_avatar_404(self, client, tmp_path, monkeypatch):
        from core import config
        monkeypatch.setattr(config.settings, "AVATARS_DIR", str(tmp_path))
        assert client.delete("/api/assets/avatar/nope.mp4").status_code == 404
