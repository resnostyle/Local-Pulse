"""Tests for iCal handler."""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from scraper.ical_handler import (
    _event_to_dict,
    _extract_url_from_description,
    _to_naive_utc,
    fetch_ical_events,
)

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:12345
SUMMARY:Test Meeting
DTSTART:20260320T140000Z
DTEND:20260320T150000Z
DESCRIPTION:https://www.apexnc.org/calendar.aspx?EID=4496
LOCATION:Town Hall
END:VEVENT
BEGIN:VEVENT
UID:67890
SUMMARY:Another Event
DTSTART:20260321
DTEND:20260321
LOCATION:Community Center
END:VEVENT
END:VCALENDAR
"""


class TestToNaiveUtc:
    def test_datetime_with_tz(self):
        from datetime import timezone

        dt = datetime(2026, 3, 20, 14, 0, 0, tzinfo=timezone.utc)
        result = _to_naive_utc(dt)
        assert result == datetime(2026, 3, 20, 14, 0, 0)

    def test_datetime_naive(self):
        dt = datetime(2026, 3, 20, 14, 0, 0)
        result = _to_naive_utc(dt)
        assert result == datetime(2026, 3, 20, 14, 0, 0)

    def test_date_only(self):
        d = date(2026, 3, 20)
        result = _to_naive_utc(d)
        assert result == datetime(2026, 3, 20, 0, 0, 0)

    def test_none(self):
        assert _to_naive_utc(None) is None


class TestExtractUrlFromDescription:
    def test_extracts_url(self):
        desc = "Event details at https://www.apexnc.org/calendar.aspx?EID=4496"
        assert _extract_url_from_description(desc, "https://example.com") == (
            "https://www.apexnc.org/calendar.aspx?EID=4496"
        )

    def test_empty_returns_none(self):
        assert _extract_url_from_description("", "https://example.com") is None
        assert _extract_url_from_description(None, "https://example.com") is None

    def test_strips_trailing_punctuation(self):
        desc = "See (https://example.com/event) for details"
        result = _extract_url_from_description(desc, "https://x.com")
        assert result == "https://example.com/event"


class TestEventToDict:
    def test_converts_vevent(self):
        from icalendar import Calendar

        cal = Calendar.from_ical(SAMPLE_ICS)
        for comp in cal.walk():
            if comp.name == "VEVENT":
                evt = _event_to_dict(
                    comp,
                    "Town of Apex",
                    "https://www.apexnc.org",
                    "Town Hall",
                    "Apex",
                )
                if evt and evt["title"] == "Test Meeting":
                    assert evt["title"] == "Test Meeting"
                    assert evt["start_time"] == datetime(2026, 3, 20, 14, 0, 0)
                    assert evt["end_time"] == datetime(2026, 3, 20, 15, 0, 0)
                    assert "apexnc.org" in (evt["source_url"] or "")
                    assert evt["venue"] == "Town Hall"
                    assert evt["city"] == "Apex"
                    assert evt["source"] == "Town of Apex"
                    return
        pytest.fail("Test Meeting event not found")

    def test_returns_none_for_empty_summary(self):
        from icalendar import Event

        ev = Event()
        ev.add("dtstart", datetime(2026, 3, 20, 14, 0, 0))
        result = _event_to_dict(ev, "Source", "https://x.com", None, None)
        assert result is None


class TestFetchIcalEvents:
    @patch("scraper.fetcher.requests.get")
    def test_parses_ical_feed(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = SAMPLE_ICS
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_ical_events(
            "https://example.com/calendar.ics",
            "Town of Apex",
            venue="Town Hall",
            city="Apex",
        )

        assert len(events) >= 2
        titles = [e["title"] for e in events]
        assert "Test Meeting" in titles
        assert "Another Event" in titles
        assert all(e["source"] == "Town of Apex" for e in events)

    @patch("scraper.fetcher.requests.get")
    def test_returns_empty_on_fetch_failure(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("Connection failed")

        events = fetch_ical_events("https://example.com/calendar.ics", "Test")
        assert events == []

    @patch("scraper.fetcher.requests.get")
    def test_returns_empty_on_parse_failure(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "not valid ical"
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_ical_events("https://example.com/bad.ics", "Test")
        assert events == []

    @patch("scraper.fetcher.requests.get")
    def test_deduplicates_by_uid(self, mock_get):
        dup_ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:same
SUMMARY:First
DTSTART:20260320T140000Z
END:VEVENT
BEGIN:VEVENT
UID:same
SUMMARY:Duplicate
DTSTART:20260320T150000Z
END:VEVENT
END:VCALENDAR
"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = dup_ics
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status = lambda: None

        events = fetch_ical_events("https://example.com/dup.ics", "Test")
        assert len(events) == 1
