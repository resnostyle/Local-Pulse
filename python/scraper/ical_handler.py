"""Fetch and parse iCal (.ics) feeds into event dicts."""

import logging
import re
from datetime import date, datetime, timezone

from typing import Optional
from urllib.parse import urlparse

from icalendar import Calendar

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"


def _to_naive_utc(dt) -> Optional[datetime]:
    """Convert icalendar datetime/date to naive UTC datetime."""
    if dt is None:
        return None
    if hasattr(dt, "dt"):
        dt = dt.dt
    if isinstance(dt, datetime):
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(dt, datetime.min.time())
    return None


def _extract_url_from_description(desc: str, base_url: str) -> Optional[str]:
    """Extract event URL from DESCRIPTION."""
    if not desc:
        return None
    # Common pattern: URL at start of description
    m = re.search(r"https?://[^\s\)\]\"']+", desc.strip())
    if m:
        return m.group(0).rstrip('.,;)]}\'"')
    return None


def _event_to_dict(component, source_name: str, base_url: str, venue: Optional[str], city: Optional[str]) -> Optional[dict]:
    """Convert iCal VEVENT to our event format."""
    summary = component.get("summary")
    if not summary:
        return None
    title = str(summary).strip()
    if not title:
        return None

    dtstart = component.get("dtstart")
    start_dt = _to_naive_utc(dtstart)
    if start_dt is None:
        return None

    dtend = component.get("dtend")
    end_dt = _to_naive_utc(dtend) if dtend else None

    location = component.get("location")
    venue_str = str(location).strip() if location else venue
    if venue_str and len(venue_str) > 255:
        venue_str = venue_str[:252] + "..."

    desc = component.get("description")
    desc_str = str(desc).strip() if desc else None
    source_url = _extract_url_from_description(desc_str or "", base_url)
    if not source_url and base_url:
        uid = component.get("uid")
        if uid:
            eid = str(uid).strip()
            # CivicEngage-style URL pattern used by many municipal sites
            if eid.isdigit() and base_url:
                source_url = f"{base_url.rstrip('/')}/calendar.aspx?EID={eid}"

    recurring = component.get("rrule") is not None or component.get("recurrence-id") is not None

    return {
        "title": title,
        "description": desc_str,
        "start_time": start_dt,
        "end_time": end_dt,
        "venue": venue_str or None,
        "city": city,
        "category": None,
        "source": source_name,
        "source_url": source_url or base_url,
        "recurring": recurring,
    }


def fetch_ical_events(
    url: str,
    source_name: str,
    venue: Optional[str] = None,
    city: Optional[str] = None,
    base_url: Optional[str] = None,
) -> list[dict]:
    """Fetch iCal feed and return event dicts.

    Args:
        url: Full URL to .ics feed
        source_name: Source label for events
        venue: Default venue (overridden by LOCATION if present)
        city: Default city
        base_url: Base URL for building event links (e.g. https://example.com)

    Returns:
        List of event dicts ready for insert.
    """
    from .fetcher import fetch_with_conditional

    ics_text = fetch_with_conditional(url, timeout=DEFAULT_TIMEOUT, user_agent=USER_AGENT)
    if ics_text is None:
        return []

    if not base_url:
        # Extract origin (e.g. https://www.apexnc.org) for building event links
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    try:
        cal = Calendar.from_ical(ics_text)
    except ValueError as e:
        logger.warning("iCal parse failed %s: %s", url, e)
        return []

    events = []
    seen_uids = set()
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = component.get("uid")
        uid_str = str(uid) if uid else None
        if uid_str and uid_str in seen_uids:
            continue
        if uid_str:
            seen_uids.add(uid_str)

        evt = _event_to_dict(component, source_name, base_url, venue, city)
        if evt:
            events.append(evt)

    logger.info("Parsed %d events from iCal %s", len(events), url)
    return events
