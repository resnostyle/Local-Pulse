"""Tests for scraper orchestration."""

from unittest.mock import patch

import pytest

from scraper.scraper import fetch_events_for_source


class TestFetchEventsForSource:
    def test_missing_url_returns_empty(self):
        result = fetch_events_for_source({"source": "X", "type": "rss"})
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
        mock_fetch_rss.assert_called_once_with("https://example.com/feed", "X")

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
    def test_html_fetch_failure_returns_empty(self, mock_fetch):
        mock_fetch.return_value = None
        result = fetch_events_for_source({
            "url": "https://example.com/calendar",
            "source": "X",
            "type": "html",
        })
        assert result == []

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
