"""Per-source operational state in meta/sources/{name}.json (replaces MySQL for prod)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pipeline.paths import meta_sources_dir
from pipeline.raw_writer import slug_segment

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 5


def _meta_path(source_name: str) -> Path:
    return meta_sources_dir() / f"{slug_segment(source_name)}.json"


def _empty_meta(source_name: str) -> dict[str, Any]:
    return {
        "source": source_name,
        "retry_count": 0,
        "max_retries": DEFAULT_MAX_RETRIES,
        "backoff_until": None,
        "last_run_at": None,
        "last_status": None,
        "etag": None,
        "last_modified": None,
    }


def load_source_meta(source_name: str) -> dict[str, Any]:
    path = _meta_path(source_name)
    if not path.is_file():
        return _empty_meta(source_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        base = _empty_meta(source_name)
        base.update(data)
        base["source"] = source_name
        return base
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read meta for %s: %s", source_name, e)
        return _empty_meta(source_name)


def save_source_meta(source_name: str, meta: dict[str, Any]) -> None:
    path = _meta_path(source_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "source": source_name}
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_iso(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    s = dt_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_source_due(source: dict, meta: dict, *, force: bool = False) -> bool:
    if force:
        return True
    if source.get("enabled") is False:
        return False
    backoff = _parse_iso(meta.get("backoff_until"))
    if backoff and datetime.now(timezone.utc) < backoff:
        return False
    interval = int(source.get("interval_minutes", 360))
    last_run = _parse_iso(meta.get("last_run_at"))
    if last_run is None:
        return True
    return datetime.now(timezone.utc) >= last_run + timedelta(minutes=interval)


def get_fetch_metadata(source_name: str) -> Optional[dict]:
    meta = load_source_meta(source_name)
    etag = meta.get("etag")
    last_modified = meta.get("last_modified")
    if not etag and not last_modified:
        return None
    return {"etag": etag, "last_modified": last_modified}


def set_fetch_metadata(
    source_name: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> None:
    meta = load_source_meta(source_name)
    meta["etag"] = etag
    meta["last_modified"] = last_modified
    save_source_meta(source_name, meta)


def record_run_result(
    source_name: str,
    *,
    status: str,
    events_found: int = 0,
    duration_ms: int = 0,
    error_message: str | None = None,
) -> None:
    """Update meta after a scrape attempt."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = load_source_meta(source_name)
    meta["last_run_at"] = now
    meta["last_status"] = status
    meta["last_events_found"] = events_found
    meta["last_duration_ms"] = duration_ms
    if error_message:
        meta["last_error"] = error_message[:2000]

    if status in ("success", "no_change"):
        meta["retry_count"] = 0
        meta["backoff_until"] = None
    elif status == "error":
        new_count = int(meta.get("retry_count", 0)) + 1
        max_retries = int(meta.get("max_retries", DEFAULT_MAX_RETRIES))
        meta["retry_count"] = new_count
        if new_count >= max_retries:
            meta["enabled"] = False
            logger.warning("Source %s disabled after %d consecutive failures", source_name, new_count)
        else:
            backoff_seconds = min(60 * (2**new_count), 86400)
            until = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            meta["backoff_until"] = until.strftime("%Y-%m-%dT%H:%M:%SZ")

    save_source_meta(source_name, meta)
