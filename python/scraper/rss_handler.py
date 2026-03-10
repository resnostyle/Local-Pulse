"""Parse RSS/Atom feeds into event dicts."""

import logging
import re
from datetime import datetime
from html import unescape
from typing import Optional

import feedparser
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"
)

# Visit Raleigh embeds dates like "01/05/2026 to 03/31/2026" or "Starting 03/09/2026"
DATE_RANGE_RE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
STARTING_RE = re.compile(
    r"Starting\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)


def _parse_date(s: str) -> Optional[datetime]:
    """Parse MM/DD/YYYY to datetime (UTC)."""
    try:
        dt = datetime.strptime(s.strip(), "%m/%d/%Y")
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        return None


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


def fetch_and_parse(url: str, source_name: str) -> list[dict]:
    """Fetch RSS feed and parse into event dicts.

    Args:
        url: RSS feed URL
        source_name: Human-readable source name (e.g. "Visit Raleigh")

    Returns:
        List of event dicts with keys: title, description, start_time, end_time,
        venue, city, category, source, source_url
    """
    try:
        resp = requests.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Failed to fetch RSS %s: %s", url, e)
        return []

    feed = feedparser.parse(resp.content)
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
            start_time = pub_date or datetime.utcnow()

        categories = entry.get("tags", [])
        category = None
        if categories:
            cat = categories[0] if isinstance(categories[0], str) else categories[0].get("term", "")
            category = cat.strip() if cat else None

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
        })

    logger.info("Parsed %d events from RSS %s", len(events), url)
    return events
