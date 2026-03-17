"""Tests for config module."""

import tempfile
from pathlib import Path

import pytest

from config import load_calendar_sources


def test_load_calendar_sources_returns_list():
    sources = load_calendar_sources()
    assert isinstance(sources, list)
    assert len(sources) > 0, "calendars.yaml should have sources (packaging/path regression)"


def test_load_calendar_sources_has_expected_structure():
    """Calendars.yaml should have source, type for each entry. url required for rss, html, ical, nmc_json."""
    sources = load_calendar_sources()
    assert sources, "calendar config not found - test requires calendars.yaml"
    valid_types = ("rss", "html", "espn", "ical", "nmc_json")
    for s in sources:
        assert "source" in s
        assert "type" in s
        assert s["type"] in valid_types
        # rss, html, ical, nmc_json require url; espn does not
        if s["type"] in ("rss", "html", "ical", "nmc_json"):
            assert "url" in s


def test_load_calendar_sources_missing_file(monkeypatch):
    """When calendars.yaml is missing, returns empty list."""
    import config
    with tempfile.TemporaryDirectory() as tmp:
        fake_init = Path(tmp) / "config" / "__init__.py"
        fake_init.parent.mkdir(parents=True, exist_ok=True)
        fake_init.touch()
        monkeypatch.setattr(config, "__file__", str(fake_init))
        result = config.load_calendar_sources()
        assert result == []
