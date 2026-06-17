"""Unit tests for the pure SRT helpers in the translator and TTS services."""
from services.translator.translator import parse_srt, build_srt, _parse_numbered_response
from services.tts.tts_service import _parse_srt_for_tts, _srt_time_to_seconds


class TestParseSrt:
    def test_parses_all_blocks(self, tmp_srt):
        segs = parse_srt(tmp_srt.read_text(encoding="utf-8"))
        assert len(segs) == 3
        assert segs[0]["index"] == 1
        assert segs[0]["text"] == "Hello and welcome."
        assert segs[2]["timecode"] == "00:00:07,000 --> 00:00:12,500"

    def test_multiline_text_joined(self):
        srt = "1\n00:00:00,000 --> 00:00:02,000\nline one\nline two\n"
        segs = parse_srt(srt)
        assert segs[0]["text"] == "line one line two"

    def test_skips_malformed_blocks(self):
        srt = "not a number\n00:00:00,000 --> 00:00:02,000\ntext\n\n2\n00:00:02,000 --> 00:00:03,000\nok\n"
        segs = parse_srt(srt)
        assert len(segs) == 1
        assert segs[0]["index"] == 2

    def test_empty_input(self):
        assert parse_srt("") == []


class TestBuildSrt:
    def test_roundtrip(self, tmp_srt):
        original = tmp_srt.read_text(encoding="utf-8")
        segs = parse_srt(original)
        rebuilt = build_srt(segs)
        # Re-parsing the rebuilt output yields identical segments
        assert parse_srt(rebuilt) == segs


class TestParseNumberedResponse:
    def test_extracts_numbered_lines(self):
        text = "1. 你好\n2. 世界\n3. 测试"
        assert _parse_numbered_response(text, 3) == ["你好", "世界", "测试"]

    def test_pads_when_fewer_returned(self):
        out = _parse_numbered_response("1. only one", 3)
        assert out == ["only one", "", ""]

    def test_truncates_when_more_returned(self):
        out = _parse_numbered_response("1. a\n2. b\n3. c\n4. d", 2)
        assert out == ["a", "b"]

    def test_ignores_non_numbered_noise(self):
        text = "Here are the translations:\n1. 甲\n2. 乙\nThanks!"
        assert _parse_numbered_response(text, 2) == ["甲", "乙"]


class TestSrtTimeConversion:
    def test_basic(self):
        assert _srt_time_to_seconds("00:00:02,000") == 2.0
        assert _srt_time_to_seconds("00:01:30,500") == 90.5
        assert _srt_time_to_seconds("01:00:00,000") == 3600.0

    def test_parse_srt_for_tts(self, tmp_srt):
        segs = _parse_srt_for_tts(str(tmp_srt))
        assert len(segs) == 3
        assert segs[0]["start"] == 0.0
        assert segs[0]["end"] == 2.0
        assert segs[2]["end"] == 12.5
        assert segs[1]["text"] == "This is a test of the system."
