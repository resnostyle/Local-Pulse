"""Tests for config module."""

from pathlib import Path

import pytest

from config import load_calendar_sources


def test_load_calendar_sources_returns_list():
    sources = load_calendar_sources()
    assert isinstance(sources, list)


def test_load_calendar_sources_has_expected_structure():
    """Calendars.yaml should have url, source, type for each entry."""
    sources = load_calendar_sources()
    if not sources:
        pytest.skip("calendar config not found")
    for s in sources:
        assert "url" in s
        assert "source" in s
        assert "type" in s
        assert s["type"] in ("rss", "html")
