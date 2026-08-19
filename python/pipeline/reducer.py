"""Rebuild public events JSON from raw runs (full compile, no incremental patch)."""

from __future__ import annotations

import json
import logging
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.dedupe import processed_event_id, start_date_key
from pipeline.paths import events_root, location_events_dir, raw_root
from pipeline.raw_writer import slug_segment

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def discover_locations(root: Path | None = None) -> list[tuple[str, str]]:
    """List (state, city) slug pairs present under raw/."""
    base = root if root is not None else raw_root()
    if not base.is_dir():
        return []
    locations: list[tuple[str, str]] = []
    for state_dir in sorted(base.iterdir()):
        if not state_dir.is_dir():
            continue
        for city_dir in sorted(state_dir.iterdir()):
            if city_dir.is_dir():
                locations.append((state_dir.name, city_dir.name))
    return locations


def _read_raw_records(state: str, city: str, root: Path | None = None) -> list[dict]:
    loc_dir = (root if root is not None else raw_root()) / state / city
    if not loc_dir.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(loc_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Skipping bad raw file %s: %s", path, e)
            continue
        for rec in payload.get("records") or []:
            if isinstance(rec, dict):
                records.append(rec)
    return records


def _dedupe_records(records: list[dict]) -> dict[str, dict]:
    """Last record wins for duplicate event IDs."""
    by_id: dict[str, dict] = {}
    for rec in records:
        eid = processed_event_id(rec)
        if eid is None:
            continue
        out = {k: v for k, v in rec.items() if k != "raw_hash"}
        out["id"] = eid
        by_id[eid] = out
    return by_id


def reduce_location(
    state: str,
    city: str,
    *,
    raw: Path | None = None,
    events: Path | None = None,
) -> int:
    """Full rebuild of processed JSON for one location. Returns event count."""
    records = _read_raw_records(state, city, raw)
    by_id = _dedupe_records(records)
    loc_dir = location_events_dir(state, city) if events is None else (
        events / "locations" / slug_segment(state) / slug_segment(city)
    )

    by_date_dir = loc_dir / "by-date"
    by_id_dir = loc_dir / "by-id"

    if by_date_dir.is_dir():
        shutil.rmtree(by_date_dir)
    if by_id_dir.is_dir():
        shutil.rmtree(by_id_dir)
    by_date_dir.mkdir(parents=True, exist_ok=True)
    by_id_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for eid, evt in sorted(by_id.items(), key=lambda x: x[1].get("start_time") or ""):
        day = start_date_key(evt)
        if day:
            grouped[day].append(evt)
        (by_id_dir / f"{eid}.json").write_text(
            json.dumps(evt, indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )

    dates_sorted = sorted(grouped.keys())
    for day in dates_sorted:
        day_file = by_date_dir / f"{day}.json"
        day_file.write_text(
            json.dumps(
                {"date": day, "events": grouped[day]},
                indent=2,
                ensure_ascii=False,
                default=_json_default,
            ),
            encoding="utf-8",
        )

    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    loc_index = {
        "state": slug_segment(state),
        "city": slug_segment(city),
        "dates": dates_sorted,
        "event_count": len(by_id),
        "updated_at": updated_at,
    }
    loc_dir.mkdir(parents=True, exist_ok=True)
    (loc_dir / "index.json").write_text(
        json.dumps(loc_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "Reduced %s/%s: %d events across %d dates",
        state,
        city,
        len(by_id),
        len(dates_sorted),
    )
    return len(by_id)


def reduce_all(*, raw: Path | None = None, events: Path | None = None) -> dict[str, int]:
    """Rebuild all locations found under raw/ and update events/index.json."""
    ev_root = events if events is not None else events_root()
    ev_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    locations: list[dict[str, str]] = []

    for state, city in discover_locations(raw):
        count = reduce_location(state, city, raw=raw, events=ev_root)
        counts[f"{state}/{city}"] = count
        if count > 0 or (raw or raw_root()) / state / city:
            locations.append({"state": state, "city": city})

    global_index = {
        "locations": sorted(locations, key=lambda x: (x["state"], x["city"])),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (ev_root / "index.json").write_text(
        json.dumps(global_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return counts
