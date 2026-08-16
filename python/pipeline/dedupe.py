"""Deterministic event IDs for the file pipeline (todo.txt dedup strategy)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional


def _normalize_start(value: Any) -> Optional[str]:
    """Normalize start_time to a stable UTC string for fingerprinting."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                parse_s = s[:10] if fmt == "%Y-%m-%d" else s
                dt = datetime.strptime(parse_s, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo:
        offset = dt.utcoffset() or timedelta(0)
        dt = dt.replace(tzinfo=None) - offset
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _hash_parts(*parts: str) -> str:
    payload = "".join(f"{len(p)}:{p}" for p in parts)
    return hashlib.sha256(payload.encode()).hexdigest()


def processed_event_id(record: dict) -> Optional[str]:
    """Return a stable event ID, or None if the record lacks required fields.

    Primary: title + start_time + venue (todo.txt content hash).
    Fallback: source + source_id (event-level id or source_url).
    Last resort: raw_hash from the raw writer.
    """
    title = (record.get("title") or "").strip()
    start = _normalize_start(record.get("start_time"))
    venue = (record.get("venue") or "").strip()
    source = (record.get("source") or "").strip()
    source_id = (record.get("event_source_id") or record.get("source_id") or "").strip()
    if not source_id:
        source_id = (record.get("source_url") or "").strip()

    if title and start and venue:
        return _hash_parts(title, start, venue)
    if source and source_id:
        return _hash_parts(source, source_id)
    raw_hash = record.get("raw_hash")
    if isinstance(raw_hash, str) and raw_hash:
        return raw_hash
    if title and start:
        return _hash_parts(title, start, (record.get("source_url") or ""))
    return None


def start_date_key(record: dict) -> Optional[str]:
    """YYYY-MM-DD for grouping processed by-date files."""
    start = _normalize_start(record.get("start_time"))
    if not start:
        return None
    return start[:10]
