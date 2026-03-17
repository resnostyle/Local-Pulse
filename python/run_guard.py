"""Rate limiting and mutex per endpoint to avoid abusing external servers.

- Rate limit: minimum interval between runs per endpoint (configurable).
- Mutex: file lock prevents concurrent runs on the same endpoint.
- Use --only to run specific sources; --force to bypass rate limit.
"""

import json
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from time import time
from urllib.parse import urlparse

from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)

# State dir under project (python/.run_guard/ or .local-pulse/)
_BASE = Path(__file__).resolve().parent / ".run_guard"
STATE_FILE = _BASE / "run_state.json"
FETCH_METADATA_FILE = _BASE / "fetch_metadata.json"
LOCK_DIR = _BASE / "locks"
STATE_LOCK_PATH = _BASE / "state.lock"

DEFAULT_MIN_INTERVAL_SECONDS = 3600  # 1 hour between runs per endpoint


def _ensure_dirs() -> None:
    _BASE.mkdir(parents=True, exist_ok=True)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)


def _with_state_lock(fn, fallback=None):
    """Acquire global state lock, run fn(), release. On Timeout, log and return fallback."""
    _ensure_dirs()
    lock = FileLock(STATE_LOCK_PATH)
    try:
        lock.acquire(timeout=10)
    except Timeout:
        logger.warning("State lock timeout: %s", STATE_LOCK_PATH)
        return fallback
    try:
        return fn()
    finally:
        lock.release()


def endpoint_id(source: dict) -> str:
    """Derive a stable identifier for rate limiting and locking.

    Uses source name (e.g. ESPN, Visit Raleigh) or URL host for sources without name.
    """
    name = source.get("source", "").strip()
    if name:
        # Normalize: lowercase, replace spaces with underscore, remove special chars
        return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_")) or "unknown"
    url = source.get("url", "")
    if url:
        try:
            netloc = urlparse(url).netloc
            return re.sub(r"[^a-z0-9_.-]", "", netloc.lower()) or "unknown"
        except (ValueError, TypeError) as e:
            logger.debug("endpoint_id urlparse failed for %r: %s", url, e)
    return "unknown"


def _load_state() -> dict:
    """Load last-run timestamps per endpoint."""
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load run state: %s", e)
        return {}


def _save_state(state: dict) -> None:
    """Persist last-run timestamps."""
    _ensure_dirs()
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.warning("Could not save run state: %s", e)


def _load_fetch_metadata() -> dict:
    """Load ETag/Last-Modified per URL for conditional requests."""
    if not FETCH_METADATA_FILE.exists():
        return {}
    try:
        with open(FETCH_METADATA_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Could not load fetch metadata: %s", e)
        return {}


def _save_fetch_metadata(metadata: dict) -> None:
    """Persist fetch metadata."""
    _ensure_dirs()
    try:
        with open(FETCH_METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
    except OSError as e:
        logger.warning("Could not save fetch metadata: %s", e)


def get_fetch_metadata(url: str) -> dict | None:
    """Get stored ETag/Last-Modified for a URL. Returns None if none stored."""
    def _get():
        meta = _load_fetch_metadata()
        return meta.get(url)

    return _with_state_lock(_get, fallback=None)


def set_fetch_metadata(url: str, etag: str | None, last_modified: str | None) -> None:
    """Store ETag and/or Last-Modified for a URL after a successful 200 response."""

    def _set():
        meta = _load_fetch_metadata()
        entry = meta.setdefault(url, {})
        if etag is not None:
            entry["etag"] = etag
        if last_modified is not None:
            entry["last_modified"] = last_modified
        if entry:
            _save_fetch_metadata(meta)

    _with_state_lock(_set, fallback=None)


def should_run(endpoint_id_key: str, min_interval_seconds: float, force: bool = False) -> bool:
    """Return True if we're allowed to run this endpoint (rate limit check)."""
    if force:
        return True

    def _check():
        state = _load_state()
        return state.get(endpoint_id_key)

    last = _with_state_lock(_check, fallback=time())
    if last is None:
        return True
    elapsed = time() - last
    if elapsed < min_interval_seconds:
        logger.info(
            "Skipping %s: last run %.0f min ago (min interval %.0f min)",
            endpoint_id_key,
            elapsed / 60,
            min_interval_seconds / 60,
        )
        return False
    return True


def record_run(endpoint_id_key: str) -> None:
    """Record that we ran this endpoint (for rate limiting)."""
    def _do_record():
        state = _load_state()
        state[endpoint_id_key] = time()
        _save_state(state)

    _with_state_lock(_do_record, fallback=None)


def acquire_endpoint_lock(endpoint_id_key: str, timeout: float = 0) -> FileLock | None:
    """Acquire an exclusive lock for this endpoint. Returns lock or None if already held.

    timeout=0 means fail immediately if lock is held.
    Caller must call lock.release() when done.
    """
    _ensure_dirs()
    lock_path = LOCK_DIR / f"{endpoint_id_key}.lock"
    lock = FileLock(lock_path)
    try:
        lock.acquire(timeout=timeout)
        return lock
    except Timeout:
        logger.info("Skipping %s: another process is already running it", endpoint_id_key)
        return None


@contextmanager
def run_guard(
    source: dict,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    force: bool = False,
):
    """Context manager: acquire lock and check rate limit before running a source.

    Yields (True, endpoint_id) if we should run, (False, endpoint_id) if skipped.
    On successful yield True, records the run on exit.
    """
    eid = endpoint_id(source)
    if not should_run(eid, min_interval_seconds, force):
        yield False, eid
        return

    lock = acquire_endpoint_lock(eid)
    if lock is None:
        yield False, eid
        return

    try:
        yield True, eid
    finally:
        try:
            record_run(eid)
        except Exception as e:
            logger.warning("record_run failed: %s", e)
        lock.release()
