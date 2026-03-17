"""Tests for run_guard (rate limit, mutex)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from run_guard import acquire_endpoint_lock, endpoint_id, record_run, run_guard, should_run


class TestEndpointId:
    def test_uses_source_name(self):
        assert endpoint_id({"source": "ESPN"}) == "espn"
        assert endpoint_id({"source": "Visit Raleigh"}) == "visit_raleigh"

    def test_uses_url_netloc_when_no_source(self):
        assert endpoint_id({"url": "https://example.com/feed"}) == "example.com"
        assert endpoint_id({"url": "https://www.visitraleigh.com/event/rss/"}) == "www.visitraleigh.com"

    def test_unknown_when_empty(self):
        assert endpoint_id({}) == "unknown"


class TestShouldRun:
    def test_first_run_allowed(self):
        with patch("run_guard._load_state", return_value={}):
            assert should_run("espn", 3600, force=False) is True

    def test_force_bypasses_rate_limit(self):
        with patch("run_guard._load_state", return_value={"espn": 1.0}):
            assert should_run("espn", 3600, force=True) is True

    def test_recent_run_blocks(self):
        import time
        with patch("run_guard._load_state", return_value={"espn": time.time() - 60}):
            assert should_run("espn", 3600, force=False) is False

    def test_old_run_allows(self):
        import time
        with patch("run_guard._load_state", return_value={"espn": time.time() - 4000}):
            assert should_run("espn", 3600, force=False) is True


class TestRecordRun:
    def test_updates_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_file = base / "run_state.json"
            lock_dir = base / "locks"
            state_lock = base / "state.lock"
            lock_dir.mkdir()
            with patch("run_guard.STATE_FILE", state_file), patch(
                "run_guard.LOCK_DIR", lock_dir
            ), patch("run_guard.STATE_LOCK_PATH", state_lock):
                record_run("espn")
            assert state_file.exists()
            data = json.loads(state_file.read_text())
            assert "espn" in data
            assert isinstance(data["espn"], (int, float))


class TestAcquireEndpointLock:
    def test_acquires_lock_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            lock_dir.mkdir()
            with patch("run_guard.LOCK_DIR", lock_dir):
                lock = acquire_endpoint_lock("test_endpoint", timeout=0)
            assert lock is not None
            lock.release()

    def test_returns_none_when_lock_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            lock_dir.mkdir()
            with patch("run_guard.LOCK_DIR", lock_dir):
                first = acquire_endpoint_lock("contended", timeout=0)
                assert first is not None
                second = acquire_endpoint_lock("contended", timeout=0)
                assert second is None
                first.release()


class TestRunGuard:
    def test_yields_true_when_should_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lock_dir = base / "locks"
            state_lock = base / "state.lock"
            lock_dir.mkdir()
            with patch("run_guard._load_state", return_value={}), patch(
                "run_guard.acquire_endpoint_lock"
            ) as mock_acquire:
                mock_lock = MagicMock()
                mock_acquire.return_value = mock_lock
                with patch("run_guard.STATE_FILE", base / "run_state.json"), patch(
                    "run_guard.LOCK_DIR", lock_dir
                ), patch("run_guard.STATE_LOCK_PATH", state_lock):
                    with run_guard({"source": "ESPN"}, min_interval_seconds=3600, force=False) as (
                        ok,
                        eid,
                    ):
                        assert ok is True
                        assert eid == "espn"
                mock_lock.release.assert_called()

    def test_yields_false_when_rate_limited(self):
        import time

        with patch("run_guard._load_state", return_value={"espn": time.time() - 60}):
            with run_guard({"source": "ESPN"}, min_interval_seconds=3600, force=False) as (
                ok,
                eid,
            ):
                assert ok is False
                assert eid == "espn"

    def test_yields_false_when_lock_unavailable(self):
        with patch("run_guard._load_state", return_value={}), patch(
            "run_guard.acquire_endpoint_lock", return_value=None
        ):
            with run_guard({"source": "ESPN"}, min_interval_seconds=3600, force=False) as (
                ok,
                eid,
            ):
                assert ok is False
                assert eid == "espn"

    def test_force_bypasses_rate_limit_and_runs(self):
        import time

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lock_dir = base / "locks"
            state_lock = base / "state.lock"
            lock_dir.mkdir()
            with patch("run_guard._load_state", return_value={"espn": time.time() - 60}), patch(
                "run_guard.acquire_endpoint_lock"
            ) as mock_acquire:
                mock_lock = MagicMock()
                mock_acquire.return_value = mock_lock
                with patch("run_guard.STATE_FILE", base / "run_state.json"), patch(
                    "run_guard.LOCK_DIR", lock_dir
                ), patch("run_guard.STATE_LOCK_PATH", state_lock):
                    with run_guard({"source": "ESPN"}, min_interval_seconds=3600, force=True) as (
                        ok,
                        eid,
                    ):
                        assert ok is True
                        assert eid == "espn"
