"""Tests for RSS handler."""

from datetime import datetime
from unittest.mock import patch

import pytest

from scraper.rss_handler import (
    _extract_dates_from_description,
    _extract_times_from_visitraleigh_page,
    _parse_date,
    _parse_times_str,
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


class TestParseTimesStr:
    def test_single_time(self):
        assert _parse_times_str("7pm") == ((19, 0), None)
        assert _parse_times_str("Mon., 7pm") == ((19, 0), None)
        assert _parse_times_str("5:30pm") == ((17, 30), None)
        assert _parse_times_str("11am") == ((11, 0), None)

    def test_range_format(self):
        assert _parse_times_str("7-8pm") == ((19, 0), (20, 0))
        assert _parse_times_str("Mon., 7-8pm") == ((19, 0), (20, 0))

    def test_skips_placeholder(self):
        assert _parse_times_str("All day") is None
        assert _parse_times_str("TBD") is None
        assert _parse_times_str("TBA") is None


class TestOvernightEventEndTime:
    """Ensure overnight events (e.g. 11pm-1am) get end_time > start_time."""

    @patch("scraper.rss_handler.requests.get")
    def test_overnight_event_end_after_start(self, mock_get):
        from scraper.rss_handler import _enrich_visitraleigh_event

        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.text = '''
        <li class="times"><span class="info-list-value">11pm-1am</span></li>
        '''
        event = {
            "title": "Late Night",
            "start_time": datetime(2026, 3, 16, 0, 0, 0),
            "end_time": datetime(2026, 3, 16, 0, 0, 0),
            "source_url": "https://www.visitraleigh.com/event/late-night/123/",
        }
        _enrich_visitraleigh_event(event, crawl_delay=0)
        assert event["start_time"] < event["end_time"]
        # 11pm Mar 16 ET -> 11pm UTC (EST) or 3am Mar 17 UTC (EDT); 1am Mar 17 ET -> next day
        assert event["end_time"].day >= event["start_time"].day


class TestExtractTimesFromVisitRaleighPage:
    def test_extracts_from_li_times(self):
        html = '''
        <li class="info-list-item times">
            <span class="info-list-label"><strong>Times:</strong></span>
            <span class="info-list-value">Mon., 7pm</span>
        </li>
        '''
        assert _extract_times_from_visitraleigh_page(html) == ((19, 0), None)

    def test_extracts_range(self):
        html = '''
        <li class="times">
            <span class="info-list-value">7-8pm</span>
        </li>
        '''
        assert _extract_times_from_visitraleigh_page(html) == ((19, 0), (20, 0))

    def test_returns_none_when_no_times(self):
        html = "<html><body><p>No times here</p></body></html>"
        assert _extract_times_from_visitraleigh_page(html) is None


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
        # Minimal Event has no pub_date/description dates - should be skipped (no datetime.utcnow fallback)
        assert "Minimal Event" not in titles

    @patch("scraper.rss_handler.requests.get")
    def test_returns_empty_on_fetch_failure(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")

        events = fetch_and_parse("https://example.com/feed", "Test")
        assert events == []
