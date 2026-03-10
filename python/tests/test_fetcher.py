"""Tests for HTML fetcher."""

from unittest.mock import patch

import pytest

from scraper.fetcher import extract_text, fetch_html


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
        mock_get.return_value.text = "<html><body>Hello</body></html>"
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
        mock_get.return_value.text = "OK"
        mock_get.return_value.raise_for_status = lambda: None

        fetch_html("https://example.com")
        call_kwargs = mock_get.call_args[1]
        assert "User-Agent" in call_kwargs["headers"]
        assert "LocalPulse" in call_kwargs["headers"]["User-Agent"]
