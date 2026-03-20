"""Parse RSS/Atom feeds into event dicts."""

import logging
import re
import time as _time
from datetime import datetime, timedelta
from html import unescape
from typing import Optional
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

from .fetcher import get_crawl_delay

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"
)

# Common RSS patterns: "01/05/2026 to 03/31/2026" or "Starting 03/09/2026"
DATE_RANGE_RE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
STARTING_RE = re.compile(
    r"Starting\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)

# Time patterns: "7pm", "7:30pm", "7-8pm", "7-8:30pm", "5:00-8:30pm"
TIME_PART_RE = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
    re.IGNORECASE,
)
# Range format: "7-8pm" or "7:30-8:45pm" (shared am/pm)
TIME_RANGE_RE = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
    re.IGNORECASE,
)
RALEIGH_TZ = ZoneInfo("America/New_York")


def _parse_date(s: str) -> Optional[datetime]:
    """Parse MM/DD/YYYY to datetime (UTC)."""
    try:
        dt = datetime.strptime(s.strip(), "%m/%d/%Y")
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        return None


def _parse_time_to_minutes(hour: int, minute: int, ampm: str) -> int:
    """Convert hour, minute, am/pm to minutes since midnight."""
    if ampm.lower() == "pm" and hour != 12:
        hour += 12
    elif ampm.lower() == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute


def _parse_times_str(s: str) -> Optional[tuple[tuple[int, int], Optional[tuple[int, int]]]]:
    """Parse time string like '7pm', '7-8pm', 'Mon., 7pm' into (start_hour, start_min), (end_hour, end_min)|None."""
    if not s or not s.strip():
        return None
    s = s.strip()
    # Skip "All day", "TBD", "TBA", etc.
    if re.search(r"all\s*day|tbd|tba|varies|to\s*be\s*announced", s, re.I):
        return None
    # Try range format first: "7-8pm" or "7:30-8:45pm"
    range_m = TIME_RANGE_RE.search(s)
    if range_m:
        start = _parse_time_to_minutes(
            int(range_m.group(1)), int(range_m.group(2) or 0), range_m.group(5)
        )
        end = _parse_time_to_minutes(
            int(range_m.group(3)), int(range_m.group(4) or 0), range_m.group(5)
        )
        return divmod(start, 60), divmod(end, 60)
    # Single time: "7pm" or "7:30pm"
    parts = TIME_PART_RE.findall(s)
    if not parts:
        return None
    start = _parse_time_to_minutes(int(parts[0][0]), int(parts[0][1] or 0), parts[0][2])
    start_h, start_m = divmod(start, 60)
    if len(parts) >= 2:
        end = _parse_time_to_minutes(int(parts[1][0]), int(parts[1][1] or 0), parts[1][2])
        end_h, end_m = divmod(end, 60)
        return (start_h, start_m), (end_h, end_m)
    return (start_h, start_m), None


def _extract_times_from_event_page(html: str) -> Optional[tuple[tuple[int, int], Optional[tuple[int, int]]]]:
    """Extract start/end time from event page HTML (looks for li.times span.value structure)."""
    soup = BeautifulSoup(html, "html.parser")
    for li in soup.find_all("li", class_=lambda c: c and "times" in str(c).lower()):
        val = li.find("span", class_=lambda c: c and "value" in str(c).lower())
        if val:
            return _parse_times_str(val.get_text())
    text = soup.get_text()
    m = re.search(r"Times:\s*([^\n]+)", text)
    return _parse_times_str(m.group(1).strip()) if m else None


def _enrich_event_with_times(event: dict, tz: ZoneInfo = RALEIGH_TZ, crawl_delay: float = 0.3) -> None:
    """Fetch event detail page and update start_time/end_time if page has times (li.times span.value)."""
    url = event.get("source_url")
    if not url:
        return
    # Only attempt for URLs that look like event detail pages (common pattern across many sites)
    if "/event/" not in url and "/events/" not in url:
        return
    start_dt = event.get("start_time")
    if not start_dt or not isinstance(start_dt, datetime):
        return
    try:
        resp = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        times = _extract_times_from_event_page(resp.text)
        if not times:
            return
        (start_h, start_m), end_times = times
        # Apply time to start_date in local timezone, then convert to UTC
        local_dt = start_dt.replace(
            hour=start_h, minute=start_m, second=0, microsecond=0, tzinfo=tz
        )
        utc_dt = local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        event["start_time"] = utc_dt
        if end_times:
            end_h, end_m = end_times
            if event.get("end_time") and isinstance(event["end_time"], datetime):
                end_dt = event["end_time"]
                base_date = end_dt if end_dt.date() != start_dt.date() else start_dt
            else:
                base_date = start_dt
            local_end = base_date.replace(
                hour=end_h, minute=end_m, second=0, microsecond=0, tzinfo=tz
            )
            # Overnight events (e.g. 11pm-1am): end time is next calendar day
            if local_end <= local_dt:
                local_end += timedelta(days=1)
            event["end_time"] = local_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    except requests.RequestException as e:
        logger.debug("Could not fetch event page %s: %s", url, e)
    finally:
        _time.sleep(crawl_delay)


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    # Simple tag strip
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(text).strip()


def _extract_dates_from_description(description: str, pub_date: Optional[datetime]) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract start_time and end_time from RSS description."""
    start, end = None, None
    desc = _strip_html(description)

    range_match = DATE_RANGE_RE.search(desc)
    if range_match:
        start = _parse_date(range_match.group(1))
        end = _parse_date(range_match.group(2))
        return start, end

    start_match = STARTING_RE.search(desc)
    if start_match:
        start = _parse_date(start_match.group(1))
        return start, None

    if pub_date:
        return pub_date, None
    return None, None


def fetch_and_parse(url: str, source_name: str, tz: str = "America/New_York", source_id: int | None = None) -> list[dict]:
    """Fetch RSS feed and parse into event dicts.

    Uses conditional fetch (ETag/Last-Modified) when available to skip
    parsing when the feed has not changed.

    Args:
        url: RSS feed URL
        source_name: Human-readable source name
        tz: Timezone for parsing times from detail pages (default America/New_York)
        source_id: DB source id for conditional fetch metadata

    Returns:
        List of event dicts with keys: title, description, start_time, end_time,
        venue, city, category, source, source_url
    """
    from .fetcher import fetch_with_conditional

    content = fetch_with_conditional(url, timeout=DEFAULT_TIMEOUT, user_agent=USER_AGENT, source_id=source_id)
    if content is None:
        return []

    feed = feedparser.parse(content)
    events = []

    for entry in feed.entries:
        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            st = entry.published_parsed
            pub_date = datetime(*st[:6])

        link = entry.get("link", url)
        title = _strip_html(entry.get("title", ""))
        if not title:
            continue

        description = _strip_html(entry.get("description", ""))
        start_time, end_time = _extract_dates_from_description(description, pub_date)

        if not start_time:
            # Skip entries without a deterministic date to avoid nondeterministic fingerprints
            continue

        categories = entry.get("tags", [])
        category = None
        if categories:
            cat = categories[0] if isinstance(categories[0], str) else categories[0].get("term", "")
            category = cat.strip() if cat else None

        recurring = bool(
            description
            and any(
                kw in description.lower()
                for kw in ("recurring", "repeats", "repeats weekly", "repeats monthly", "every week", "every month")
            )
        )
        events.append({
            "title": title,
            "description": description[:5000] if description else None,
            "start_time": start_time,
            "end_time": end_time,
            "venue": None,
            "city": None,
            "category": category,
            "source": source_name,
            "source_url": link,
            "recurring": recurring,
        })

    # Enrich events with times from detail pages when structure matches (li.times span.value)
    if events:
        sample_url = events[0].get("source_url", url)
        crawl_delay = get_crawl_delay(sample_url)
        try:
            zone = ZoneInfo(tz) if tz else RALEIGH_TZ
        except KeyError:
            zone = RALEIGH_TZ
        for evt in events:
            _enrich_event_with_times(evt, tz=zone, crawl_delay=crawl_delay)

    logger.info("Parsed %d events from RSS %s", len(events), url)
    return events
