"""Tests for raw → events reducer."""

import json
from datetime import datetime, timezone

from pipeline.paths import events_root, raw_root
from pipeline.raw_writer import write_raw_run
from pipeline.reducer import discover_locations, reduce_all, reduce_location


def test_discover_locations(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.reducer.raw_root", lambda: tmp_path)
    (tmp_path / "nc" / "raleigh").mkdir(parents=True)
    assert discover_locations() == [("nc", "raleigh")]


def test_reduce_location_writes_by_date(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALPULSE_DATA_ROOT", str(tmp_path))
    source = {"source": "Test", "state": "NC", "city": "Raleigh"}
    events = [
        {
            "title": "Concert",
            "start_time": "2026-06-15T19:00:00Z",
            "venue": "Park",
            "source": "Test",
            "source_url": "https://example.com/a",
        },
        {
            "title": "Market",
            "start_time": "2026-06-15T10:00:00Z",
            "venue": "Square",
            "source": "Test",
            "source_url": "https://example.com/b",
        },
    ]
    run_at = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    write_raw_run(source, events, run_at=run_at)

    count = reduce_location("nc", "raleigh")
    assert count == 2

    day_path = events_root() / "locations" / "nc" / "raleigh" / "by-date" / "2026-06-15.json"
    assert day_path.is_file()
    day = json.loads(day_path.read_text())
    assert day["date"] == "2026-06-15"
    assert len(day["events"]) == 2

    loc_index = events_root() / "locations" / "nc" / "raleigh" / "index.json"
    assert json.loads(loc_index.read_text())["event_count"] == 2


def test_reduce_all_global_index(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALPULSE_DATA_ROOT", str(tmp_path))
    source = {"source": "X", "state": "nc", "city": "durham"}
    write_raw_run(
        source,
        [
            {
                "title": "E",
                "start_time": "2026-07-01T12:00:00Z",
                "venue": "V",
                "source": "X",
                "source_url": "https://x.com/1",
            }
        ],
        run_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    counts = reduce_all()
    assert "nc/durham" in counts
    global_index = json.loads((events_root() / "index.json").read_text())
    assert any(loc["city"] == "durham" for loc in global_index["locations"])
