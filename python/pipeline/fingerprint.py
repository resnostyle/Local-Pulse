"""Deterministic fingerprints for raw JSON records."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Union

logger = logging.getLogger(__name__)


def compute_fingerprint(title: str, start_time: str, source_url: str) -> str:
    """SHA-256 fingerprint from title + start_time + source_url."""
    payload = f"{len(title)}:{title}{len(start_time)}:{start_time}{len(source_url)}:{source_url}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _normalize_datetime(value: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """Parse datetime or ISO string to naive UTC datetime."""
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
            logger.warning("Could not parse datetime %r", value)
            return None
    if dt.tzinfo:
        offset = dt.utcoffset() or timedelta(0)
        dt = dt.replace(tzinfo=None) - offset
    return dt


def _format_datetime(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def event_fingerprint(evt: dict) -> Optional[str]:
    """Return raw_hash for an event dict, or None if required fields are missing."""
    title = evt.get("title", "")
    start_time = evt.get("start_time")
    source_url = evt.get("source_url", "")
    if not title or not start_time:
        return None
    start_dt = _normalize_datetime(start_time)
    if start_dt is None:
        return None
    return compute_fingerprint(title, _format_datetime(start_dt), source_url)
