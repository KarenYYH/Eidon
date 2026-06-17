"""Shared fixtures. Ensures backend/ is importable and points temp/output dirs
at a throwaway location so tests never pollute real artifacts."""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return BACKEND_DIR / "temp" / "_fixtures"


@pytest.fixture
def tmp_srt(tmp_path) -> Path:
    """A minimal valid English SRT file."""
    content = (
        "1\n00:00:00,000 --> 00:00:02,000\nHello and welcome.\n\n"
        "2\n00:00:02,000 --> 00:00:07,000\nThis is a test of the system.\n\n"
        "3\n00:00:07,000 --> 00:00:12,500\nIt should work end to end.\n"
    )
    p = tmp_path / "subtitles.srt"
    p.write_text(content, encoding="utf-8")
    return p
