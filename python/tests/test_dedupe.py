"""Tests for file-pipeline deduplication IDs."""

from pipeline.dedupe import processed_event_id, start_date_key


def test_primary_key_title_start_venue():
    rec = {
        "title": "Food Festival",
        "start_time": "2026-03-24T18:00:00Z",
        "venue": "Downtown",
        "source": "eventbrite",
        "source_url": "https://example.com/1",
    }
    fp1 = processed_event_id(rec)
    fp2 = processed_event_id({**rec, "source_url": "https://other.com"})
    assert fp1 is not None
    assert fp1 == fp2


def test_fallback_source_and_url():
    rec = {
        "title": "Gig",
        "start_time": "2026-03-15T14:00:00",
        "source": "My Feed",
        "source_url": "https://example.com/event/99",
    }
    eid = processed_event_id(rec)
    assert eid is not None
    assert len(eid) == 64


def test_raw_hash_last_resort():
    rec = {"title": "X", "start_time": "2026-01-01", "raw_hash": "abc" * 10 + "abcd"}
    assert processed_event_id(rec) == rec["raw_hash"]


def test_start_date_key():
    assert start_date_key({"start_time": "2026-06-11T14:00:00Z"}) == "2026-06-11"
