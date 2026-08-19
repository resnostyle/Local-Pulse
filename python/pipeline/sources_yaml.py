"""Load calendar sources from YAML (production path without MySQL)."""

from __future__ import annotations

from config import load_calendar_sources


def calendar_entry_to_source(cal: dict) -> dict:
    """Convert one calendars.yaml entry to scraper source dict."""
    name = (cal.get("source") or "").strip()
    source: dict = {
        "source": name,
        "type": cal.get("type", "html"),
        "url": cal.get("url", "") or "",
        "interval_minutes": cal.get("interval_minutes", 360),
        "enabled": cal.get("enabled", True),
    }
    skip = {"source", "type", "url", "interval_minutes", "enabled"}
    for key, value in cal.items():
        if key not in skip:
            source[key] = value
    return source


def load_sources_from_yaml() -> list[dict]:
    """All calendar entries as scraper-ready dicts."""
    return [calendar_entry_to_source(c) for c in load_calendar_sources() if c.get("source")]
