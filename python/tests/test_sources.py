"""Tests for db.sources CRUD and sync logic."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_cursor(rows=None, fetchone_val=None):
    """Build a mock cursor context manager returning preset rows."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = fetchone_val
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_mock_conn(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


class TestSyncFromYaml:
    @patch("db.sources._conn")
    def test_inserts_new_sources(self, mock_conn_fn):
        cursor = _make_mock_cursor(rows=[])
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import sync_from_yaml

        calendars = [
            {"source": "ESPN", "type": "espn", "interval_minutes": 120},
            {"source": "Visit Raleigh", "type": "rss", "url": "https://example.com/rss", "interval_minutes": 360},
        ]
        sync_from_yaml(calendars)

        insert_calls = [
            c for c in cursor.execute.call_args_list if "INSERT INTO sources" in str(c)
        ]
        assert len(insert_calls) == 2
        conn.commit.assert_called_once()

    @patch("db.sources._conn")
    def test_disables_removed_sources(self, mock_conn_fn):
        cursor = _make_mock_cursor(rows=[{"id": 1, "name": "Old Source"}])
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import sync_from_yaml

        sync_from_yaml([{"source": "ESPN", "type": "espn"}])

        disable_calls = [
            c
            for c in cursor.execute.call_args_list
            if "enabled = 0" in str(c) and "Old Source" in str(c)
        ]
        assert len(disable_calls) == 1

    @patch("db.sources._conn")
    def test_updates_existing_sources(self, mock_conn_fn):
        cursor = _make_mock_cursor(rows=[{"id": 1, "name": "ESPN"}])
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import sync_from_yaml

        sync_from_yaml([{"source": "ESPN", "type": "espn", "interval_minutes": 60}])

        update_calls = [
            c for c in cursor.execute.call_args_list if "UPDATE sources" in str(c) and "source_type" in str(c)
        ]
        assert len(update_calls) == 1


class TestRecordRun:
    @patch("db.sources._conn")
    def test_records_success_resets_retry(self, mock_conn_fn):
        cursor = _make_mock_cursor()
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import record_run

        record_run(source_id=1, status="success", events_found=10, events_inserted=5, duration_ms=1200)

        insert_calls = [c for c in cursor.execute.call_args_list if "INSERT INTO scrape_runs" in str(c)]
        assert len(insert_calls) == 1

        reset_calls = [c for c in cursor.execute.call_args_list if "retry_count = 0" in str(c)]
        assert len(reset_calls) == 1
        conn.commit.assert_called_once()

    @patch("db.sources._conn")
    def test_records_error_increments_backoff(self, mock_conn_fn):
        cursor = _make_mock_cursor(fetchone_val={"retry_count": 1, "max_retries": 5})
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import record_run

        record_run(source_id=1, status="error", error_message="Connection timeout", duration_ms=500)

        backoff_calls = [c for c in cursor.execute.call_args_list if "backoff_until" in str(c)]
        assert len(backoff_calls) == 1

    @patch("db.sources._conn")
    def test_disables_source_after_max_retries(self, mock_conn_fn):
        cursor = _make_mock_cursor(fetchone_val={"retry_count": 4, "max_retries": 5})
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import record_run

        record_run(source_id=1, status="error", error_message="Persistent failure")

        disable_calls = [c for c in cursor.execute.call_args_list if "enabled = 0" in str(c)]
        assert len(disable_calls) == 1


class TestGetFetchMetadata:
    @patch("db.sources._conn")
    def test_returns_metadata(self, mock_conn_fn):
        cursor = _make_mock_cursor(fetchone_val={"etag": '"abc123"', "last_modified": "Thu, 01 Jan 2026"})
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import get_fetch_metadata

        result = get_fetch_metadata(1)
        assert result["etag"] == '"abc123"'
        assert result["last_modified"] == "Thu, 01 Jan 2026"

    @patch("db.sources._conn")
    def test_returns_none_when_not_found(self, mock_conn_fn):
        cursor = _make_mock_cursor(fetchone_val=None)
        conn = _make_mock_conn(cursor)
        mock_conn_fn.return_value = conn

        from db.sources import get_fetch_metadata

        assert get_fetch_metadata(999) is None
