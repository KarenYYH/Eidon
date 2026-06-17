"""Unit tests for ffmpeg_mix helpers (pure / fast paths)."""
import pytest

from services.synthesizer import ffmpeg_mix


class TestEscapeSubtitlePath:
    def test_posix_path_unchanged(self):
        assert ffmpeg_mix._escape_subtitle_path("/tmp/a/sub.srt") == "/tmp/a/sub.srt"

    def test_windows_drive_colon_escaped(self):
        assert ffmpeg_mix._escape_subtitle_path(r"C:\videos\sub.srt") == "C\\:/videos/sub.srt"

    def test_backslashes_normalised(self):
        assert ffmpeg_mix._escape_subtitle_path(r"a\b\c.srt") == "a/b/c.srt"


class TestHasSubtitlesFilter:
    async def test_returns_bool_and_caches(self, monkeypatch):
        calls = {"n": 0}

        class FakeProc:
            returncode = 0
            async def communicate(self):
                calls["n"] += 1
                return (b" subtitles  V->V  burn subs\n", b"")

        async def fake_exec(*a, **k):
            return FakeProc()

        monkeypatch.setattr(ffmpeg_mix.asyncio, "create_subprocess_exec", fake_exec)
        ffmpeg_mix._subtitles_filter_available = None  # reset cache

        assert await ffmpeg_mix._has_subtitles_filter() is True
        assert await ffmpeg_mix._has_subtitles_filter() is True
        assert calls["n"] == 1  # cached after first probe

    async def test_detects_missing_filter(self, monkeypatch):
        class FakeProc:
            returncode = 0
            async def communicate(self):
                return (b" anull  A->A  pass\n", b"")

        async def fake_exec(*a, **k):
            return FakeProc()

        monkeypatch.setattr(ffmpeg_mix.asyncio, "create_subprocess_exec", fake_exec)
        ffmpeg_mix._subtitles_filter_available = None
        assert await ffmpeg_mix._has_subtitles_filter() is False
