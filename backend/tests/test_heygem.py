"""Unit tests for the HeyGem digital-human service (mocked HTTP)."""
from pathlib import Path

import httpx
import pytest

import services.lipsync.heygem as hg


def _make_files(tmp_path):
    audio = tmp_path / "narration.wav"
    audio.write_bytes(b"RIFF....fake wav")
    avatar = tmp_path / "face.mp4"
    avatar.write_bytes(b"fake mp4")
    return str(audio), str(avatar)


class FakeResp:
    def __init__(self, json_data=None, content=b""):
        self._json = json_data or {}
        self.content = content
    def raise_for_status(self):
        pass
    def json(self):
        return self._json


def _client_factory(post_resp, query_sequence, download_content=b"VIDEO"):
    """Build a fake AsyncClient class scripted with submit/query/download responses."""
    state = {"q": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass
        async def post(self, url, json=None):
            return FakeResp(post_resp)
        async def get(self, url, params=None):
            # /easy/query polls, or a result download URL
            if url.endswith("/easy/query"):
                i = min(state["q"], len(query_sequence) - 1)
                state["q"] += 1
                return FakeResp(query_sequence[i])
            return FakeResp(content=download_content)

    return FakeClient


async def test_requires_audio_and_avatar(tmp_path):
    with pytest.raises(RuntimeError, match="音频"):
        await hg.generate_digital_human("", "x", "job")
    audio, _ = _make_files(tmp_path)
    with pytest.raises(RuntimeError, match="人脸"):
        await hg.generate_digital_human(audio, "", "job")


async def test_success_with_url_result(tmp_path, monkeypatch):
    audio, avatar = _make_files(tmp_path)
    monkeypatch.setattr(hg.settings, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(hg.settings, "HEYGEM_POLL_INTERVAL", 0.01)
    fake = _client_factory(
        post_resp={"success": True, "code": 10000},
        query_sequence=[
            {"data": {"status": 1}},                                   # pending
            {"data": {"status": 2, "result": "http://h/result.mp4"}},  # done
        ],
        download_content=b"DIGITAL_HUMAN_VIDEO",
    )
    monkeypatch.setattr(httpx, "AsyncClient", fake)

    out = await hg.generate_digital_human(audio, avatar, "job1")
    assert Path(out).exists()
    assert Path(out).read_bytes() == b"DIGITAL_HUMAN_VIDEO"


async def test_submit_rejected(tmp_path, monkeypatch):
    audio, avatar = _make_files(tmp_path)
    monkeypatch.setattr(hg.settings, "TEMP_DIR", str(tmp_path / "temp"))
    fake = _client_factory(post_resp={"success": False, "code": 500}, query_sequence=[{}])
    monkeypatch.setattr(httpx, "AsyncClient", fake)
    with pytest.raises(RuntimeError, match="submit rejected"):
        await hg.generate_digital_human(audio, avatar, "job2")


async def test_synthesis_failed_status(tmp_path, monkeypatch):
    audio, avatar = _make_files(tmp_path)
    monkeypatch.setattr(hg.settings, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(hg.settings, "HEYGEM_POLL_INTERVAL", 0.01)
    fake = _client_factory(
        post_resp={"success": True, "code": 10000},
        query_sequence=[{"data": {"status": 3}}],
    )
    monkeypatch.setattr(httpx, "AsyncClient", fake)
    with pytest.raises(RuntimeError, match="synthesis failed"):
        await hg.generate_digital_human(audio, avatar, "job3")


async def test_poll_timeout(tmp_path, monkeypatch):
    audio, avatar = _make_files(tmp_path)
    monkeypatch.setattr(hg.settings, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(hg.settings, "HEYGEM_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(hg.settings, "HEYGEM_TIMEOUT", 0.0)  # immediate timeout
    fake = _client_factory(
        post_resp={"success": True, "code": 10000},
        query_sequence=[{"data": {"status": 1}}],
    )
    monkeypatch.setattr(httpx, "AsyncClient", fake)
    with pytest.raises(TimeoutError):
        await hg.generate_digital_human(audio, avatar, "job4")


async def test_local_path_result_copied(tmp_path, monkeypatch):
    audio, avatar = _make_files(tmp_path)
    monkeypatch.setattr(hg.settings, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(hg.settings, "HEYGEM_POLL_INTERVAL", 0.01)
    # server returns a local filesystem path that exists on this host
    server_result = tmp_path / "server_out.mp4"
    server_result.write_bytes(b"LOCAL_RESULT")
    fake = _client_factory(
        post_resp={"success": True, "code": 10000},
        query_sequence=[{"data": {"status": 2, "result": str(server_result)}}],
    )
    monkeypatch.setattr(httpx, "AsyncClient", fake)
    out = await hg.generate_digital_human(audio, avatar, "job5")
    assert Path(out).read_bytes() == b"LOCAL_RESULT"
