"""Tests for HTML fetcher."""

from unittest.mock import patch

import pytest

from scraper.fetcher import (
    DEFAULT_CRAWL_DELAY,
    extract_text,
    fetch_html,
    fetch_with_conditional,
    get_crawl_delay,
)


class TestExtractText:
    def test_extracts_visible_text(self):
        html = "<html><body><h1>Event Title</h1><p>Event description here.</p></body></html>"
        text = extract_text(html)
        assert "Event Title" in text
        assert "Event description here" in text

    def test_strips_script_and_style(self):
        html = """
        <html><body>
        <script>alert('x');</script>
        <style>.x { color: red; }</style>
        <p>Visible</p>
        </body></html>
        """
        text = extract_text(html)
        assert "Visible" in text
        assert "alert" not in text
        assert "color" not in text

    def test_empty_html(self):
        assert extract_text("") == ""
        assert extract_text("<html></html>") == ""


class TestFetchHtml:
    @patch("scraper.fetcher.requests.get")
    def test_returns_html_on_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<html><body>Hello</body></html>"
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        result = fetch_html("https://example.com")
        assert result == "<html><body>Hello</body></html>"

    @patch("scraper.fetcher.requests.get")
    def test_returns_none_on_failure(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")

        result = fetch_html("https://example.com")
        assert result is None

    @patch("scraper.fetcher.requests.get")
    def test_passes_user_agent(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "OK"
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        fetch_html("https://example.com")
        call_kwargs = mock_get.call_args[1]
        assert "User-Agent" in call_kwargs["headers"]
        assert "LocalPulse" in call_kwargs["headers"]["User-Agent"]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 30

    @patch("scraper.fetcher.requests.get")
    @patch("run_guard.get_fetch_metadata")
    @patch("run_guard.set_fetch_metadata")
    def test_returns_none_on_304_not_modified(self, mock_set, mock_get_meta, mock_get):
        mock_get_meta.return_value = {"etag": "abc"}
        mock_get.return_value.status_code = 304

        result = fetch_with_conditional("https://example.com/feed")
        assert result is None
        mock_set.assert_not_called()


class TestGetCrawlDelay:
    @patch("scraper.fetcher.requests.get")
    def test_returns_crawl_delay_from_robots_txt(self, mock_get):
        mock_get.return_value.text = "User-agent: *\nCrawl-delay: 2\n"
        mock_get.return_value.raise_for_status = lambda: None

        assert get_crawl_delay("https://www.visitraleigh.com/event/foo/") == 2.0

    @patch("scraper.fetcher.requests.get")
    def test_returns_default_when_no_crawl_delay(self, mock_get):
        mock_get.return_value.text = "User-agent: *\nDisallow: /admin/\n"
        mock_get.return_value.raise_for_status = lambda: None

        assert get_crawl_delay("https://example.com/page") == DEFAULT_CRAWL_DELAY

    @patch("scraper.fetcher.requests.get")
    def test_returns_default_on_fetch_failure(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")

        assert get_crawl_delay("https://example.com/") == DEFAULT_CRAWL_DELAY

    @patch("scraper.fetcher.requests.get")
    def test_clamps_delay_to_reasonable_range(self, mock_get):
        mock_get.return_value.text = "Crawl-delay: 300\n"
        mock_get.return_value.raise_for_status = lambda: None

        assert get_crawl_delay("https://example.com/") == 60.0

    @patch("scraper.fetcher.requests.get")
    def test_clamps_delay_to_minimum(self, mock_get):
        mock_get.return_value.text = "Crawl-delay: 0.05\n"
        mock_get.return_value.raise_for_status = lambda: None

        assert get_crawl_delay("https://example.com/") == 0.1
