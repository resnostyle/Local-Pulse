"""Fetch events from NMC-style JSON API (e.g. Downtown Cary Park)."""

import html
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"
DEFAULT_TZ = ZoneInfo("America/New_York")
DEFAULT_DAYS_AHEAD = 90


def _parse_dt(s: str, tz: ZoneInfo = DEFAULT_TZ) -> datetime | None:
    """Parse ISO datetime string (assume local if no tz) and return naive UTC."""
    if not s or not s.strip():
        return None
    s = s.strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    # Convert to naive UTC
    dt = dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return dt


def _event_to_dict(
    item: dict,
    source_name: str,
    venue: str | None,
    city: str | None,
    tz: ZoneInfo = DEFAULT_TZ,
    site_base_url: str | None = None,
) -> dict | None:
    """Convert NMC API event to our event format."""
    title = html.unescape(item.get("title", "")).strip()
    if not title:
        return None
    start_dt = _parse_dt(item.get("start", ""), tz=tz)
    if start_dt is None:
        return None
    end_dt = _parse_dt(item.get("end", ""), tz=tz)
    source_url = item.get("url", "").strip()
    if not source_url:
        if site_base_url:
            source_url = f"{site_base_url.rstrip('/')}/things-to-do/calendar/"
        else:
            source_url = "https://downtowncarypark.com/things-to-do/calendar/"

    recurring = bool(item.get("recurring") or item.get("recurrence") or item.get("rrule"))
    return {
        "title": title,
        "description": None,
        "start_time": start_dt,
        "end_time": end_dt,
        "venue": venue,
        "city": city,
        "category": None,
        "source": source_name,
        "source_url": source_url,
        "recurring": recurring,
    }


def fetch_nmc_json_events(
    base_url: str,
    source_name: str,
    venue: str | None = "Downtown Cary Park",
    city: str | None = "Cary",
    tz: str = "America/New_York",
    days_ahead: int = DEFAULT_DAYS_AHEAD,
) -> list[dict]:
    """Fetch events from NMC-style JSON API.

    Args:
        base_url: API base URL (e.g. https://downtowncarypark.com/wp-json/nmc-feeds/v1/events)
        source_name: Source label for events
        venue: Venue name (optional)
        city: City name (optional)
        tz: Timezone for parsing datetimes (default America/New_York)
        days_ahead: How many days ahead to fetch (default 90)

    Returns:
        List of event dicts ready for insert.
    """
    try:
        zone = ZoneInfo(tz)
    except KeyError:
        zone = DEFAULT_TZ

    now = datetime.now(zone)
    start = now
    end = now + timedelta(days=days_ahead)
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end.strftime("%Y-%m-%dT%H:%M:%S")
    offset = now.strftime("%z")  # e.g. -0500 or -0400
    if len(offset) >= 5:
        offset = f"{offset[:3]}:{offset[3:5]}"  # -05:00
    start_iso = f"{start_str}{offset}"
    end_iso = f"{end_str}{offset}"

    params = {"cb": "3", "start": start_iso, "end": end_iso}
    url = f"{base_url.rstrip('/')}?{urlencode(params)}"

    from .fetcher import fetch_with_conditional

    content = fetch_with_conditional(url, timeout=DEFAULT_TIMEOUT, user_agent=USER_AGENT)
    if content is None:
        return []

    try:
        data = json.loads(content)
    except ValueError as e:
        logger.warning("NMC JSON parse failed %s: %s", url, e)
        return []

    if not isinstance(data, list):
        logger.warning("NMC JSON expected list, got %s", type(data).__name__)
        return []

    parsed = urlparse(base_url)
    site_base_url = f"{parsed.scheme}://{parsed.netloc}"

    events = []
    for item in data:
        if not isinstance(item, dict):
            continue
        evt = _event_to_dict(item, source_name, venue, city, tz=zone, site_base_url=site_base_url)
        if evt:
            events.append(evt)

    logger.info("Parsed %d events from NMC JSON %s", len(events), base_url)
    return events
