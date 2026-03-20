"""Tests for scraper orchestration."""

from unittest.mock import patch

import pytest

from scraper.scraper import fetch_events_for_source


class TestFetchEventsForSource:
    def test_missing_url_returns_empty_for_rss(self):
        result = fetch_events_for_source({"source": "X", "type": "rss"})
        assert result == []

    def test_missing_url_returns_empty_for_ical(self):
        result = fetch_events_for_source({"source": "Town of Apex", "type": "ical"})
        assert result == []

    def test_missing_url_returns_empty_for_nmc_json(self):
        result = fetch_events_for_source({"source": "Downtown Cary Park", "type": "nmc_json"})
        assert result == []

    def test_missing_url_returns_empty_for_html(self):
        result = fetch_events_for_source({"source": "X", "type": "html"})
        assert result == []

    @patch("scraper.scraper.fetch_rss")
    def test_rss_source_calls_fetch_rss(self, mock_fetch_rss):
        mock_fetch_rss.return_value = [
            {"title": "E1", "start_time": "2026-03-15", "source_url": "https://x.com"}
        ]
        result = fetch_events_for_source({
            "url": "https://example.com/feed",
            "source": "X",
            "type": "rss",
        })
        assert result == mock_fetch_rss.return_value
        mock_fetch_rss.assert_called_once_with("https://example.com/feed", "X", tz="America/New_York", source_id=None)

    @patch("scraper.scraper.fetch_html")
    @patch("scraper.scraper.extract_text")
    def test_html_source_returns_text_and_source(self, mock_extract, mock_fetch):
        mock_fetch.return_value = "<html><body>" + "x" * 100 + "</body></html>"
        mock_extract.return_value = "Sample calendar text with enough content" + "x" * 50

        result = fetch_events_for_source({
            "url": "https://example.com/calendar",
            "source": "X",
            "type": "html",
        })

        assert isinstance(result, dict)
        assert "text" in result
        assert "source" in result
        assert result["source"]["url"] == "https://example.com/calendar"

    @patch("scraper.scraper.fetch_html")
    def test_html_fetch_failure_returns_none(self, mock_fetch):
        mock_fetch.return_value = None
        result = fetch_events_for_source({
            "url": "https://example.com/calendar",
            "source": "X",
            "type": "html",
        })
        assert result is None

    @patch("scraper.scraper.fetch_html")
    @patch("scraper.scraper.extract_text")
    def test_html_insufficient_text_returns_empty(self, mock_extract, mock_fetch):
        mock_fetch.return_value = "<html><body>short</body></html>"
        mock_extract.return_value = "short"
        result = fetch_events_for_source({
            "url": "https://example.com/calendar",
            "source": "X",
            "type": "html",
        })
        assert result == []

    @patch("scraper.scraper.fetch_espn_events")
    def test_espn_source_calls_fetch_espn_events(self, mock_fetch_espn):
        mock_fetch_espn.return_value = [
            {"title": "Game", "start_time": "2026-03-18", "source_url": "https://espn.com", "category": "Sports"},
        ]
        result = fetch_events_for_source({
            "source": "ESPN",
            "type": "espn",
        })
        assert result == mock_fetch_espn.return_value
        mock_fetch_espn.assert_called_once_with("ESPN")

    @patch("scraper.scraper.fetch_nmc_json_events")
    def test_nmc_json_source_calls_fetch_nmc_json_events(self, mock_fetch_nmc):
        mock_fetch_nmc.return_value = [
            {"title": "Event", "start_time": "2026-03-20", "source_url": "https://example.com", "venue": "Park"},
        ]
        result = fetch_events_for_source({
            "url": "https://example.com/wp-json/nmc-feeds/v1/events",
            "source": "Downtown Cary Park",
            "type": "nmc_json",
        })
        assert result == mock_fetch_nmc.return_value
        mock_fetch_nmc.assert_called_once()
        call_kw = mock_fetch_nmc.call_args[1]
        assert call_kw["base_url"] == "https://example.com/wp-json/nmc-feeds/v1/events"
        assert call_kw["source_name"] == "Downtown Cary Park"

    @patch("scraper.scraper.fetch_ical_events")
    def test_ical_source_calls_fetch_ical_events(self, mock_fetch_ical):
        mock_fetch_ical.return_value = [
            {"title": "Meeting", "start_time": "2026-03-20", "source_url": "https://example.com/event", "venue": "Town Hall"},
        ]
        result = fetch_events_for_source({
            "url": "https://example.com/calendar.ics",
            "source": "Town of Apex",
            "type": "ical",
            "city": "Apex",
        })
        assert result == mock_fetch_ical.return_value
        mock_fetch_ical.assert_called_once()
        call_kw = mock_fetch_ical.call_args[1]
        assert call_kw["url"] == "https://example.com/calendar.ics"
        assert call_kw["source_name"] == "Town of Apex"
        assert call_kw["city"] == "Apex"
