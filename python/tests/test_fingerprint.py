"""Tests for fingerprint generation."""

from pipeline.fingerprint import (
    _format_datetime,
    _normalize_datetime,
    compute_fingerprint,
    event_fingerprint,
)


def test_compute_fingerprint_returns_64_char_hex():
    fp = compute_fingerprint("Test Event", "2026-03-15T14:00:00Z", "https://example.com/1")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_compute_fingerprint_deterministic():
    fp1 = compute_fingerprint("Same Event", "2026-03-15", "https://example.com")
    fp2 = compute_fingerprint("Same Event", "2026-03-15", "https://example.com")
    assert fp1 == fp2


def test_compute_fingerprint_different_inputs_different_outputs():
    fp1 = compute_fingerprint("Event A", "2026-03-15", "https://a.com")
    fp2 = compute_fingerprint("Event B", "2026-03-15", "https://a.com")
    fp3 = compute_fingerprint("Event A", "2026-03-16", "https://a.com")
    fp4 = compute_fingerprint("Event A", "2026-03-15", "https://b.com")
    assert len({fp1, fp2, fp3, fp4}) == 4


def test_normalize_datetime_from_iso_string():
    dt = _normalize_datetime("2026-03-15T14:00:00Z")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 3 and dt.day == 15


def test_event_fingerprint_missing_fields():
    assert event_fingerprint({"title": "", "start_time": "2026-01-01"}) is None
    assert event_fingerprint({"title": "X", "start_time": ""}) is None


def test_format_datetime():
    from datetime import datetime

    assert _format_datetime(datetime(2026, 3, 15, 14, 0, 0)) == "2026-03-15 14:00:00"
    assert _format_datetime(None) is None
