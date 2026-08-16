"""Tests for append-only raw JSON runs."""

import json
from datetime import datetime, timezone

from pipeline.fingerprint import event_fingerprint
from pipeline.raw_writer import build_raw_path, slug_segment, write_raw_run


class TestSlugSegment:
    def test_whitespace(self):
        assert slug_segment(None) == "unknown"
        assert slug_segment("") == "unknown"
        assert slug_segment("  ") == "unknown"

    def test_simple(self):
        assert slug_segment("Raleigh") == "raleigh"
        assert slug_segment("NC State") == "nc_state"

    def test_special_chars(self):
        assert slug_segment("Foo! Bar?") == "foo_bar"


class TestBuildRawPath:
    def test_structure(self, tmp_path):
        p = build_raw_path(
            "NC",
            "Raleigh",
            "My Source",
            "2026-01-01T00-00-00Z",
            root=tmp_path,
        )
        assert p == tmp_path / "nc" / "raleigh" / "my_source" / "2026-01-01T00-00-00Z.json"


class TestWriteRawRun:
    def test_writes_and_raw_hash_matches(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALPULSE_RAW_ROOT", str(tmp_path))
        source = {
            "source": "Test Feed",
            "state": "NC",
            "city": "Raleigh",
        }
        events = [
            {
                "title": "Gig",
                "start_time": "2026-03-15T14:00:00Z",
                "source_url": "https://example.com/e",
                "source": "Test Feed",
            }
        ]
        run_at = datetime(2026, 4, 3, 12, 30, 45, tzinfo=timezone.utc)
        path = write_raw_run(source, events, run_at=run_at)
        assert path is not None
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["source"] == "Test Feed"
        assert "source_id" not in data
        assert data["run_at"] == "2026-04-03T12:30:45Z"
        assert len(data["records"]) == 1
        rec = data["records"][0]
        assert rec["raw_hash"] == event_fingerprint(events[0])
        assert rec["title"] == "Gig"

    def test_empty_events(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALPULSE_RAW_ROOT", str(tmp_path))
        source = {"source": "X", "state": "a", "city": "b"}
        run_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        path = write_raw_run(source, [], run_at=run_at)
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["records"] == []

    def test_skips_events_without_fingerprint(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALPULSE_RAW_ROOT", str(tmp_path))
        source = {"source": "X"}
        events = [{"title": "", "start_time": "2026-01-01", "source_url": "https://x.com"}]
        run_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        path = write_raw_run(source, events, run_at=run_at)
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["records"] == []
