"""Tests for config module."""

import tempfile
from pathlib import Path

import yaml

from config import load_calendar_sources

SAMPLE_CALENDARS = {
    "calendars": [
        {"source": "Test RSS", "type": "rss", "url": "https://example.com/feed", "interval_minutes": 360},
        {"source": "Test ESPN", "type": "espn", "interval_minutes": 120},
    ]
}


def _with_config_dir(tmp_path, data=None):
    """Point config.__file__ at tmp_path, optionally write a calendars.yaml."""
    if data is not None:
        (tmp_path / "calendars.yaml").write_text(yaml.dump(data))
    import config
    orig = config.__file__
    config.__file__ = str(tmp_path / "__init__.py")
    return config, orig


def test_load_calendar_sources_returns_list(tmp_path):
    config, orig = _with_config_dir(tmp_path, SAMPLE_CALENDARS)
    try:
        sources = load_calendar_sources()
    finally:
        config.__file__ = orig
    assert isinstance(sources, list)
    assert len(sources) == 2


def test_load_calendar_sources_has_expected_structure(tmp_path):
    config, orig = _with_config_dir(tmp_path, SAMPLE_CALENDARS)
    try:
        sources = load_calendar_sources()
    finally:
        config.__file__ = orig

    valid_types = ("rss", "html", "espn", "ical", "nmc_json")
    for s in sources:
        assert "source" in s
        assert "type" in s
        assert s["type"] in valid_types
        if s["type"] in ("rss", "html", "ical", "nmc_json"):
            assert "url" in s


def test_load_calendar_sources_missing_file(tmp_path):
    """When calendars.yaml is missing, returns empty list."""
    config, orig = _with_config_dir(tmp_path)
    try:
        result = load_calendar_sources()
    finally:
        config.__file__ = orig
    assert result == []
