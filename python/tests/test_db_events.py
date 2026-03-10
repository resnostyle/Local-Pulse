"""Tests for database events module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from db.events import insert_events


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
