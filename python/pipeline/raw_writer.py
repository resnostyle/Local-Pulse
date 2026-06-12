"""Append-only raw JSON runs under raw/{state}/{city}/{source}/{run_id}.json."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.events import event_fingerprint

logger = logging.getLogger(__name__)


def _raw_root() -> Path:
    """Root directory for raw runs. Default: ./raw under cwd.

    Set LOCALPULSE_RAW_ROOT or RAW_OUTPUT_ROOT to override.
    """
    root = os.environ.get("LOCALPULSE_RAW_ROOT") or os.environ.get("RAW_OUTPUT_ROOT")
    if root:
        return Path(root).expanduser().resolve()
    return Path.cwd() / "raw"


def slug_segment(value: str | None) -> str:
    """Lowercase path segment: alnum only, single underscores; unknown if empty."""
    if value is None:
        return "unknown"
    s = str(value).strip().lower()
    if not s:
        return "unknown"
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown"


def build_raw_path(
    state: str | None,
    city: str | None,
    source_name: str | None,
    run_id: str,
    root: Path | None = None,
) -> Path:
    """Path raw/{state}/{city}/{source}/{run_id}.json under root."""
    base = root if root is not None else _raw_root()
    return (
        base
        / slug_segment(state)
        / slug_segment(city)
        / slug_segment(source_name)
        / f"{run_id}.json"
    )


def _run_id_for_filename(when: datetime) -> str:
    """UTC timestamp safe for filenames (colons replaced)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    return when.strftime("%Y-%m-%dT%H-%M-%SZ")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _records_with_hashes(events: list[dict]) -> list[dict]:
    """Events insert_events would accept, each with raw_hash added."""
    out: list[dict] = []
    for evt in events:
        fp = event_fingerprint(evt)
        if fp is None:
            continue
        rec = {**evt, "raw_hash": fp}
        out.append(rec)
    return out


def write_raw_run(
    source: dict,
    events: list[dict],
    run_at: datetime | None = None,
) -> Path | None:
    """Write one raw JSON file for this scrape run. Returns path or None on failure.

    Best-effort: logs and returns None if the write fails (disk full, permissions).
    """
    when = run_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    run_id = _run_id_for_filename(when)
    state = source.get("state")
    city = source.get("city")
    source_label = source.get("source", "unknown")
    path = build_raw_path(state, city, source_label, run_id)

    payload = {
        "run_at": when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source_label,
        "source_id": source.get("id"),
        "records": _records_with_hashes(events),
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )
        logger.info("Wrote raw run to %s", path)
        return path
    except OSError as e:
        logger.warning("Raw JSON write failed (%s): %s", path, e)
        return None
