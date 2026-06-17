"""Unit tests for the口播稿 rewriter parsing + guards (no live LLM)."""
import pytest

import services.script.rewriter as rw


class TestParseScripts:
    def test_parses_json_object_with_scripts_key(self):
        raw = '{"scripts": ["第一条口播", "第二条口播", "第三条口播"]}'
        out = rw._parse_scripts(raw, 3)
        assert out == ["第一条口播", "第二条口播", "第三条口播"]

    def test_parses_bare_json_array(self):
        out = rw._parse_scripts('["a", "b"]', 5)
        assert out == ["a", "b"]

    def test_strips_markdown_fences(self):
        raw = '```json\n{"scripts": ["x", "y"]}\n```'
        assert rw._parse_scripts(raw, 2) == ["x", "y"]

    def test_truncates_to_count(self):
        raw = '{"scripts": ["1", "2", "3", "4"]}'
        assert rw._parse_scripts(raw, 2) == ["1", "2"]

    def test_fallback_splits_numbered_text(self):
        raw = "1. 第一条\n2. 第二条\n3. 第三条"
        out = rw._parse_scripts(raw, 3)
        assert len(out) == 3
        assert "第一条" in out[0]

    def test_fallback_single_blob(self):
        out = rw._parse_scripts("just one block of text", 3)
        assert len(out) == 1


class TestGuards:
    async def test_empty_text_raises(self, monkeypatch):
        monkeypatch.setattr(rw.settings, "LLM_API_KEY", "sk-x")
        with pytest.raises(ValueError, match="原始口播稿为空"):
            await rw.rewrite_scripts("   ", 3)

    async def test_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(rw.settings, "LLM_API_KEY", "")
        with pytest.raises(RuntimeError, match="LLM API Key"):
            await rw.rewrite_scripts("some text", 3)

    async def test_calls_llm_and_returns_scripts(self, monkeypatch):
        """Mock the OpenAI client; verify count clamp + parse wiring."""
        monkeypatch.setattr(rw.settings, "LLM_API_KEY", "sk-x")

        class FakeMsg:
            content = '{"scripts": ["改写1", "改写2"]}'
        class FakeChoice:
            message = FakeMsg()
        class FakeResp:
            choices = [FakeChoice()]
        class FakeCompletions:
            async def create(self, **kw):
                FakeCompletions.kw = kw
                return FakeResp()
        class FakeChat:
            completions = FakeCompletions()
        class FakeClient:
            chat = FakeChat()
            def __init__(self, **kw): pass

        import openai
        monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)

        out = await rw.rewrite_scripts("原始稿内容", 2, style="第一人称", language="zh")
        assert out == ["改写1", "改写2"]
        # style instruction made it into the prompt
        prompt = FakeCompletions.kw["messages"][1]["content"]
        assert "第一人称" in prompt
