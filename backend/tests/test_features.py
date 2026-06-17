"""Unit tests for the new feature helpers: subtitle style, BGM volume,
aspect resolution, stock provider, publish guards (all mocked, no network)."""
import pytest

from services.synthesizer import ffmpeg_mix as fm
from services.script.scene_assembler import _resolution, ASPECT_RESOLUTIONS
import services.media.stock as stock
import services.publish.upload_post as pub


class TestSubtitleStyle:
    def test_hex_to_ass_bgr(self):
        assert fm._hex_to_ass_colour("#FF0000") == "&H0000FF&"   # red → BGR
        assert fm._hex_to_ass_colour("#00FF00") == "&H00FF00&"
        assert fm._hex_to_ass_colour("#1A2B3C") == "&H3C2B1A&"

    def test_hex_invalid_falls_back_white(self):
        assert fm._hex_to_ass_colour("bad") == "&HFFFFFF&"

    def test_force_style_uses_defaults(self, monkeypatch):
        monkeypatch.setattr(fm.settings, "SUBTITLE_FONT", "Heiti SC")
        monkeypatch.setattr(fm.settings, "SUBTITLE_POSITION", "bottom")
        monkeypatch.setattr(fm.settings, "SUBTITLE_FONT_SIZE", 24)
        s = fm._build_force_style(None)
        assert "FontName=Heiti SC" in s
        assert "FontSize=24" in s
        assert "Alignment=2" in s          # bottom

    def test_force_style_overrides_and_position(self):
        s = fm._build_force_style({"position": "top", "font_size": 40, "color": "#FF0000"})
        assert "FontSize=40" in s
        assert "Alignment=8" in s          # top
        assert "PrimaryColour=&H0000FF&" in s

    def test_center_alignment(self):
        assert "Alignment=5" in fm._build_force_style({"position": "center"})


class TestAspectResolution:
    def test_known_aspects(self):
        assert _resolution("9:16") == (1080, 1920)
        assert _resolution("16:9") == (1920, 1080)
        assert _resolution("1:1") == (1080, 1080)

    def test_unknown_defaults_portrait(self):
        assert _resolution("weird") == ASPECT_RESOLUTIONS["9:16"]


class TestStockEnabled:
    def test_disabled_when_flag_off(self, monkeypatch):
        monkeypatch.setattr(stock.settings, "STOCK_ENABLED", False)
        assert stock.is_enabled() is False

    def test_pexels_needs_key(self, monkeypatch):
        monkeypatch.setattr(stock.settings, "STOCK_ENABLED", True)
        monkeypatch.setattr(stock.settings, "STOCK_PROVIDER", "pexels")
        monkeypatch.setattr(stock.settings, "PEXELS_API_KEY", "")
        assert stock.is_enabled() is False
        monkeypatch.setattr(stock.settings, "PEXELS_API_KEY", "k")
        assert stock.is_enabled() is True

    async def test_fetch_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setattr(stock.settings, "STOCK_ENABLED", False)
        assert await stock.fetch_clip(["city"], "9:16", "job") is None

    async def test_fetch_returns_none_on_empty_keywords(self, monkeypatch):
        monkeypatch.setattr(stock.settings, "STOCK_ENABLED", True)
        monkeypatch.setattr(stock.settings, "PEXELS_API_KEY", "k")
        assert await stock.fetch_clip([], "9:16", "job") is None

    async def test_pexels_search_parses_link(self, monkeypatch):
        monkeypatch.setattr(stock.settings, "STOCK_ENABLED", True)
        monkeypatch.setattr(stock.settings, "STOCK_PROVIDER", "pexels")
        monkeypatch.setattr(stock.settings, "PEXELS_API_KEY", "k")

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"videos": [{"video_files": [
                    {"width": 720, "link": "http://v/small.mp4"},
                    {"width": 1080, "link": "http://v/big.mp4"},
                ]}]}
        class FakeClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): pass
            async def get(self, url, headers=None): return FakeResp()
        monkeypatch.setattr(stock.httpx, "AsyncClient", FakeClient)

        url = await stock._search_pexels("city night", "9:16")
        assert url == "http://v/big.mp4"   # highest width first


class TestPublishGuards:
    def test_not_configured(self, monkeypatch):
        monkeypatch.setattr(pub.settings, "UPLOAD_POST_API_KEY", "")
        assert pub.is_configured() is False

    async def test_publish_requires_key(self, monkeypatch):
        monkeypatch.setattr(pub.settings, "UPLOAD_POST_API_KEY", "")
        with pytest.raises(RuntimeError, match="UPLOAD_POST_API_KEY"):
            await pub.publish_video("/x.mp4", "t", ["tiktok"], "job")

    async def test_publish_requires_existing_file(self, monkeypatch):
        monkeypatch.setattr(pub.settings, "UPLOAD_POST_API_KEY", "k")
        with pytest.raises(RuntimeError, match="成片文件不存在"):
            await pub.publish_video("/nope.mp4", "t", ["tiktok"], "job")
