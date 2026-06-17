"""Unit tests for CosyVoice zero-shot cloning helpers (mocked HTTP)."""
import wave
from pathlib import Path

import pytest

import services.tts.tts_service as tts


def test_pcm_to_wav_roundtrip(tmp_path):
    # 0.1s of silence at 24 kHz mono int16 = 2400 samples * 2 bytes
    pcm = b"\x00\x00" * 2400
    out = tmp_path / "out.wav"
    tts._pcm_to_wav(pcm, str(out), 24000)
    assert out.exists()
    with wave.open(str(out), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == 2400


async def test_cosyvoice_requires_prompt_audio(tmp_path):
    segs = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    with pytest.raises(RuntimeError, match="参考音频"):
        await tts._tts_cosyvoice(segs, str(tmp_path / "o.wav"), "", "transcript", "job")


async def test_cosyvoice_requires_prompt_text(tmp_path):
    sample = tmp_path / "ref.wav"
    tts._pcm_to_wav(b"\x00\x00" * 100, str(sample), 24000)
    segs = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    with pytest.raises(RuntimeError, match="文字稿"):
        await tts._tts_cosyvoice(segs, str(tmp_path / "o.wav"), str(sample), "", "job")


async def test_cosyvoice_zero_shot_request(tmp_path, monkeypatch):
    """Verify the request hits /inference_zero_shot with correct form+file, and
    the streamed PCM response is wrapped to WAV and overlaid."""
    sample = tmp_path / "ref.wav"
    tts._pcm_to_wav(b"\x00\x00" * 2400, str(sample), 24000)

    captured = {}

    class FakeResp:
        content = b"\x00\x00" * 2400  # 0.1s PCM

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass
        async def post(self, url, data=None, files=None):
            captured["url"] = url
            captured["data"] = data
            captured["files_keys"] = list(files.keys()) if files else []
            return FakeResp()

    # tts imports httpx inside the function, so patch the module-level httpx
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    out = tmp_path / "dub.wav"
    segs = [{"start": 0.0, "end": 1.0, "text": "你好"}]
    result = await tts._tts_cosyvoice(segs, str(out), str(sample), "参考稿", "job")

    assert result == str(out)
    assert Path(out).exists()
    assert captured["url"].endswith("/inference_zero_shot")
    assert captured["data"]["tts_text"] == "你好"
    assert captured["data"]["prompt_text"] == "参考稿"
    assert "prompt_wav" in captured["files_keys"]
