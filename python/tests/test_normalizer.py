"""Tests for normalizer module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from normalizer.normalizer import _normalize_event, _parse_iso, normalize


class TestParseIso:
    def test_iso_with_z(self):
        result = _parse_iso("2026-03-15T14:00:00Z")
        assert result == datetime(2026, 3, 15, 14, 0, 0, 0)

    def test_iso_with_timezone_offset(self):
        result = _parse_iso("2026-03-15T14:00:00+00:00")
        assert result == datetime(2026, 3, 15, 14, 0, 0, 0)

    def test_date_only(self):
        result = _parse_iso("2026-03-15")
        assert result == datetime(2026, 3, 15, 0, 0, 0, 0)

    def test_datetime_space(self):
        result = _parse_iso("2026-03-15 14:00:00")
        assert result == datetime(2026, 3, 15, 14, 0, 0, 0)

    def test_invalid_returns_none(self):
        assert _parse_iso("") is None
        assert _parse_iso("not-a-date") is None
        assert _parse_iso(None) is None


class TestNormalizeEvent:
    def test_valid_event(self):
        item = {
            "title": "Test Event",
            "start_time": "2026-03-15T14:00:00Z",
            "description": "A great event",
            "venue": "Main Hall",
            "city": "Raleigh",
            "category": "Arts",
        }
        result = _normalize_event(item, "Test Source", "https://example.com/1")
        assert result["title"] == "Test Event"
        assert result["start_time"] == datetime(2026, 3, 15, 14, 0, 0, 0)
        assert result["description"] == "A great event"
        assert result["venue"] == "Main Hall"
        assert result["city"] == "Raleigh"
        assert result["category"] == "Arts"
        assert result["source"] == "Test Source"
        assert result["source_url"] == "https://example.com/1"

    def test_missing_title_returns_none(self):
        assert _normalize_event({"start_time": "2026-03-15"}, "S", "u") is None

    def test_missing_start_time_returns_none(self):
        assert _normalize_event({"title": "Event"}, "S", "u") is None

    def test_invalid_start_time_returns_none(self):
        assert _normalize_event(
            {"title": "Event", "start_time": "invalid"}, "S", "u"
        ) is None


class TestNormalize:
    @patch("config.OPENAI_API_KEY", "")
    def test_returns_empty_when_no_api_key(self):
        result = normalize("Some calendar text", {"source": "X", "url": "https://x.com"})
        assert result == []

    @patch("config.OPENAI_API_KEY", "sk-test")
    @patch("normalizer.normalizer.OpenAI")
    def test_parses_json_response(self, mock_openai):
        json_content = (
            '[{"title": "Event 1", "start_time": "2026-03-15T14:00:00Z", '
            '"description": "Desc", "venue": null, "city": null, "category": null}]'
        )
        mock_msg = type("Msg", (), {"content": json_content})()
        mock_choice = type("Choice", (), {"message": mock_msg})()
        mock_client = mock_openai.return_value
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        result = normalize("Calendar text here", {"source": "X", "url": "https://x.com"})

        assert len(result) == 1
        assert result[0]["title"] == "Event 1"
        assert result[0]["start_time"] == datetime(2026, 3, 15, 14, 0, 0, 0)

    @patch("config.OPENAI_API_KEY", "sk-test")
    @patch("normalizer.normalizer.OpenAI")
    def test_handles_markdown_code_block(self, mock_openai):
        content = '```json\n[{"title": "Event", "start_time": "2026-03-15T14:00:00Z"}]\n```'
        mock_msg = type("Msg", (), {"content": content})()
        mock_choice = type("Choice", (), {"message": mock_msg})()
        mock_client = mock_openai.return_value
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        result = normalize("Text", {"source": "X", "url": "https://x.com"})
        assert len(result) == 1
        assert result[0]["title"] == "Event"
