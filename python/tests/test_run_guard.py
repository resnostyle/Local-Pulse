"""Tests for run_guard (rate limit, mutex)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from run_guard import endpoint_id, record_run, should_run


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
            lock_dir.mkdir()
            with patch("run_guard.STATE_FILE", state_file), patch("run_guard.LOCK_DIR", lock_dir):
                record_run("espn")
            assert state_file.exists()
            data = json.loads(state_file.read_text())
            assert "espn" in data
            assert isinstance(data["espn"], (int, float))
