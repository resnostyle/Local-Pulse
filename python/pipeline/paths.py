"""Filesystem layout under LOCALPULSE_DATA_ROOT."""

from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    """Root for raw/, meta/, and events/. Default: ./data under cwd."""
    root = os.environ.get("LOCALPULSE_DATA_ROOT")
    if root:
        return Path(root).expanduser().resolve()
    return Path.cwd() / "data"


def raw_root() -> Path:
    """Append-only scrape runs. Overrides: LOCALPULSE_RAW_ROOT, RAW_OUTPUT_ROOT."""
    explicit = os.environ.get("LOCALPULSE_RAW_ROOT") or os.environ.get("RAW_OUTPUT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return data_root() / "raw"


def meta_root() -> Path:
    return data_root() / "meta"


def meta_sources_dir() -> Path:
    return meta_root() / "sources"


def events_root() -> Path:
    return data_root() / "events"


def location_events_dir(state: str, city: str) -> Path:
    from pipeline.raw_writer import slug_segment

    return events_root() / "locations" / slug_segment(state) / slug_segment(city)
