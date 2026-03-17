"""Tests for database events module."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from db.events import _format_datetime, _normalize_datetime, insert_events


class TestInsertEvents:
    def test_empty_list_returns_zero(self):
        with patch("db.events._conn") as mock_conn:
            result = insert_events([])
            assert result == 0
            mock_conn.assert_not_called()

    @patch("db.events._conn")
    def test_inserts_valid_events(self, mock_conn):
        cursor = MagicMock()
        cursor.execute = MagicMock()
        cursor.rowcount = 1
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.close = MagicMock()
        mock_conn.return_value = conn

        events = [
            {
                "title": "Test Event",
                "start_time": datetime(2026, 3, 15, 14, 0, 0),
                "source_url": "https://example.com/1",
                "source": "Test",
            }
        ]
        result = insert_events(events)
        assert result == 1
        cursor.execute.assert_called()
        conn.commit.assert_called()

    @patch("db.events._conn")
    def test_skips_events_missing_title_or_start_time(self, mock_conn):
        cursor = MagicMock()
        cursor.execute = MagicMock()
        cursor.rowcount = 0
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.close = MagicMock()
        mock_conn.return_value = conn

        events = [
            {"title": "", "start_time": datetime(2026, 3, 15), "source_url": "https://x.com"},
            {"title": "Valid", "start_time": None, "source_url": "https://x.com"},
        ]
        result = insert_events(events)
        assert result == 0
        cursor.execute.assert_not_called()

    @patch("db.events._conn")
    def test_skips_events_with_unparseable_start_time(self, mock_conn):
        cursor = MagicMock()
        cursor.execute = MagicMock()
        cursor.rowcount = 0
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.close = MagicMock()
        mock_conn.return_value = conn

        events = [
            {
                "title": "Bad Date",
                "start_time": "not-a-valid-datetime",
                "source_url": "https://x.com",
            },
        ]
        result = insert_events(events)
        assert result == 0
        cursor.execute.assert_not_called()

    @patch("db.events._conn")
    def test_accepts_iso_string_start_time(self, mock_conn):
        cursor = MagicMock()
        cursor.execute = MagicMock()
        cursor.rowcount = 1
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cursor
        conn.commit = MagicMock()
        conn.close = MagicMock()
        mock_conn.return_value = conn

        events = [
            {
                "title": "ISO Event",
                "start_time": "2026-03-15T14:00:00Z",
                "source_url": "https://example.com/1",
            },
        ]
        result = insert_events(events)
        assert result == 1
        cursor.execute.assert_called()


class TestNormalizeDatetime:
    def test_datetime_passthrough(self):
        dt = datetime(2026, 3, 15, 14, 0, 0)
        assert _normalize_datetime(dt) == dt

    def test_iso_with_z(self):
        result = _normalize_datetime("2026-03-15T14:00:00Z")
        assert result == datetime(2026, 3, 15, 14, 0, 0)

    def test_date_only(self):
        result = _normalize_datetime("2026-03-15")
        assert result == datetime(2026, 3, 15, 0, 0, 0)

    def test_none_returns_none(self):
        assert _normalize_datetime(None) is None

    def test_invalid_returns_none(self):
        assert _normalize_datetime("invalid") is None
        assert _normalize_datetime("") is None

    def test_timezone_aware_datetime_converts_to_utc_naive(self):
        dt = datetime(2026, 3, 15, 19, 0, 0, tzinfo=timezone(timedelta(hours=5)))
        result = _normalize_datetime(dt)
        assert result == datetime(2026, 3, 15, 14, 0, 0)
        assert result.tzinfo is None

    def test_iso_with_offset_normalizes_to_utc(self):
        result = _normalize_datetime("2026-03-15T19:00:00+05:00")
        assert result == datetime(2026, 3, 15, 14, 0, 0)
        assert result.tzinfo is None


class TestFormatDatetime:
    def test_formats_datetime(self):
        dt = datetime(2026, 3, 15, 14, 30, 0)
        assert _format_datetime(dt) == "2026-03-15 14:30:00"

    def test_none_returns_none(self):
        assert _format_datetime(None) is None
