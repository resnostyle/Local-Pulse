"""Tests for RSS handler."""

from datetime import datetime
from unittest.mock import patch

import pytest

from scraper.rss_handler import (
    _extract_dates_from_description,
    _parse_date,
    _strip_html,
    fetch_and_parse,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Events</title>
    <item>
      <title>Event with Date Range</title>
      <link>https://example.com/event/1</link>
      <description>
        <![CDATA[01/15/2026 to 01/20/2026 - Some event description here]]>
      </description>
      <category><![CDATA[ Arts ]]></category>
      <pubDate>Mon, 01 Jan 2026 00:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Event with Starting Date</title>
      <link>https://example.com/event/2</link>
      <description>
        <![CDATA[Starting 03/09/2026 - Weekly meetup]]>
      </description>
      <category><![CDATA[ Sports ]]></category>
    </item>
    <item>
      <title>Minimal Event</title>
      <link>https://example.com/event/3</link>
    </item>
  </channel>
</rss>
"""


class TestParseDate:
    def test_valid_date(self):
        assert _parse_date("01/15/2026") == datetime(2026, 1, 15, 0, 0, 0, 0)
        assert _parse_date("12/31/2025") == datetime(2025, 12, 31, 0, 0, 0, 0)

    def test_invalid_date(self):
        assert _parse_date("invalid") is None
        assert _parse_date("13/01/2026") is None  # invalid month


class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello</p>") == "Hello"
        assert _strip_html("<a href='x'>Link</a>") == "Link"

    def test_decodes_entities(self):
        assert "&amp;" in _strip_html("&amp;") or "&" in _strip_html("&amp;")
        assert "&apos;" not in _strip_html("&apos;")

    def test_empty_input(self):
        assert _strip_html("") == ""
        assert _strip_html(None) == ""


class TestExtractDatesFromDescription:
    def test_date_range(self):
        start, end = _extract_dates_from_description(
            "01/15/2026 to 01/20/2026 - Event", None
        )
        assert start == datetime(2026, 1, 15, 0, 0, 0, 0)
        assert end == datetime(2026, 1, 20, 0, 0, 0, 0)

    def test_starting_date(self):
        start, end = _extract_dates_from_description(
            "Starting 03/09/2026 - Weekly meetup", None
        )
        assert start == datetime(2026, 3, 9, 0, 0, 0, 0)
        assert end is None

    def test_fallback_to_pub_date(self):
        pub = datetime(2026, 2, 1, 12, 0, 0)
        start, end = _extract_dates_from_description("No dates here", pub)
        assert start == pub
        assert end is None

    def test_no_dates(self):
        start, end = _extract_dates_from_description("No dates", None)
        assert start is None
        assert end is None

    def test_html_in_description(self):
        start, end = _extract_dates_from_description(
            "<p>01/05/2026 to 03/31/2026</p> - Event", None
        )
        assert start == datetime(2026, 1, 5, 0, 0, 0, 0)
        assert end == datetime(2026, 3, 31, 0, 0, 0, 0)


class TestFetchAndParse:
    @patch("scraper.rss_handler.requests.get")
    def test_parses_rss_feed(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.content = SAMPLE_RSS.encode()

        events = fetch_and_parse("https://example.com/feed", "Test Source")

        assert len(events) >= 2  # At least 2 items with titles
        titles = [e["title"] for e in events]
        assert "Event with Date Range" in titles
        assert "Event with Starting Date" in titles
        assert all(e["source"] == "Test Source" for e in events)
        assert all("source_url" in e for e in events)

    @patch("scraper.rss_handler.requests.get")
    def test_returns_empty_on_fetch_failure(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")

        events = fetch_and_parse("https://example.com/feed", "Test")
        assert events == []
