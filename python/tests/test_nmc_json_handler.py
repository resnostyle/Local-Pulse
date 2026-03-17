"""Tests for NMC JSON handler."""

import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from scraper.nmc_json_handler import (
    _event_to_dict,
    _parse_dt,
    fetch_nmc_json_events,
)


class TestParseDt:
    def test_iso_with_z(self):
        result = _parse_dt("2026-03-20T14:00:00Z")
        assert result == datetime(2026, 3, 20, 14, 0, 0)

    def test_iso_local_assumes_tz(self):
        result = _parse_dt("2026-03-20T14:00:00", tz=ZoneInfo("America/New_York"))
        assert result is not None
        # 2pm EDT -> 6pm UTC (or 7pm UTC in EST)
        assert result.hour in (18, 19)

    def test_empty_returns_none(self):
        assert _parse_dt("") is None
        assert _parse_dt("   ") is None

    def test_invalid_returns_none(self):
        assert _parse_dt("not-a-date") is None


class TestEventToDict:
    def test_converts_valid_event(self):
        item = {
            "title": "Park Concert",
            "start": "2026-03-20T19:00:00",
            "end": "2026-03-20T21:00:00",
            "url": "https://downtowncarypark.com/event/123",
        }
        result = _event_to_dict(item, "Downtown Cary Park", "Downtown Cary Park", "Cary")
        assert result is not None
        assert result["title"] == "Park Concert"
        assert result["venue"] == "Downtown Cary Park"
        assert result["city"] == "Cary"
        assert result["source"] == "Downtown Cary Park"
        assert result["source_url"] == "https://downtowncarypark.com/event/123"

    def test_returns_none_for_empty_title(self):
        item = {"title": "", "start": "2026-03-20T19:00:00", "url": "https://x.com"}
        assert _event_to_dict(item, "Source", None, None) is None

    def test_returns_none_for_invalid_start(self):
        item = {"title": "Event", "start": "invalid", "url": "https://x.com"}
        assert _event_to_dict(item, "Source", None, None) is None

    def test_uses_default_source_url_when_missing(self):
        item = {"title": "Event", "start": "2026-03-20T19:00:00Z", "url": ""}
        result = _event_to_dict(item, "Downtown Cary Park", None, None)
        assert result is not None
        assert "downtowncarypark.com" in result["source_url"]

    def test_unescapes_html_in_title(self):
        item = {
            "title": "Event &amp; More",
            "start": "2026-03-20T19:00:00Z",
            "url": "https://x.com",
        }
        result = _event_to_dict(item, "Source", None, None)
        assert result is not None
        assert result["title"] == "Event & More"


class TestFetchNmcJsonEvents:
    @patch("scraper.fetcher.requests.get")
    def test_parses_json_feed(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = json.dumps([
            {
                "title": "Test Event",
                "start": "2026-03-20T19:00:00-04:00",
                "end": "2026-03-20T21:00:00-04:00",
                "url": "https://example.com/event/1",
            },
        ])
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_nmc_json_events(
            "https://example.com/wp-json/nmc-feeds/v1/events",
            "Downtown Cary Park",
            venue="Downtown Cary Park",
            city="Cary",
        )

        assert len(events) >= 1
        assert events[0]["title"] == "Test Event"
        assert events[0]["source"] == "Downtown Cary Park"

    @patch("scraper.fetcher.requests.get")
    def test_returns_empty_on_fetch_failure(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("Connection failed")

        events = fetch_nmc_json_events(
            "https://example.com/events",
            "Test",
        )
        assert events == []

    @patch("scraper.fetcher.requests.get")
    def test_returns_empty_on_non_list_response(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = json.dumps({"events": []})
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_nmc_json_events("https://example.com/events", "Test")
        assert events == []

    @patch("scraper.fetcher.requests.get")
    def test_handles_invalid_timezone(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = json.dumps([
            {
                "title": "Event",
                "start": "2026-03-20T19:00:00",
                "url": "https://x.com",
            },
        ])
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_nmc_json_events(
            "https://example.com/events",
            "Test",
            tz="Invalid/Timezone",
        )
        # Should fall back to default America/New_York
        assert len(events) >= 1
