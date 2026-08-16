"""Tests for JSON source meta files."""

import json
from datetime import datetime, timedelta, timezone

from pipeline.meta import (
    is_source_due,
    load_source_meta,
    record_run_result,
    save_source_meta,
    set_fetch_metadata,
)


def test_load_empty_meta(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.meta.meta_sources_dir", lambda: tmp_path)
    meta = load_source_meta("My Source")
    assert meta["source"] == "My Source"
    assert meta["retry_count"] == 0


def test_fetch_metadata_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.meta.meta_sources_dir", lambda: tmp_path)
    set_fetch_metadata("Feed", etag='"abc"', last_modified="Thu, 01 Jan 2026")
    path = tmp_path / "feed.json"
    data = json.loads(path.read_text())
    assert data["etag"] == '"abc"'


def test_is_source_due_respects_interval(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.meta.meta_sources_dir", lambda: tmp_path)
    now = datetime.now(timezone.utc)
    save_source_meta(
        "Feed",
        {
            "source": "Feed",
            "last_run_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "retry_count": 0,
            "backoff_until": None,
        },
    )
    source = {"source": "Feed", "interval_minutes": 360}
    assert is_source_due(source, load_source_meta("Feed")) is False
    assert is_source_due(source, load_source_meta("Feed"), force=True) is True


def test_backoff_blocks_due(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.meta.meta_sources_dir", lambda: tmp_path)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    save_source_meta(
        "Feed",
        {
            "source": "Feed",
            "backoff_until": future.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    source = {"source": "Feed", "interval_minutes": 1}
    assert is_source_due(source, load_source_meta("Feed")) is False


def test_record_run_error_increments_retry(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.meta.meta_sources_dir", lambda: tmp_path)
    record_run_result("Feed", status="error", error_message="fail")
    meta = load_source_meta("Feed")
    assert meta["retry_count"] == 1
    assert meta["backoff_until"] is not None
