"""Orchestrate scraping from calendar sources."""

import logging
from typing import Union

from .espn_handler import fetch_espn_events
from .fetcher import extract_text, fetch_html
from .ical_handler import fetch_ical_events
from .nmc_json_handler import fetch_nmc_json_events
from .rss_handler import fetch_and_parse as fetch_rss

logger = logging.getLogger(__name__)


def fetch_events_for_source(source: dict) -> Union[list[dict], dict]:
    """Fetch and parse events from a single calendar source.

    Args:
        source: Dict with url, source, type (rss, html, espn, nmc_json, or ical)

    Returns:
        For type=rss, espn, nmc_json, or ical: list of event dicts (ready to insert).
        For type=html: dict with "text" and "source" for the normalizer to process.
    """
    url = source.get("url", "")
    source_name = source.get("source", "Unknown")
    source_type = source.get("type", "html")

    if source_type == "espn":
        return fetch_espn_events(source_name)

    if source_type == "ical":
        if not url:
            logger.warning("iCal source missing url: %s", source)
            return []
        return fetch_ical_events(
            url=url,
            source_name=source_name,
            venue=source.get("venue"),
            city=source.get("city"),
            base_url=source.get("base_url"),
        )

    if source_type == "nmc_json":
        if not url:
            logger.warning("NMC JSON source missing url: %s", source)
            return []
        return fetch_nmc_json_events(
            base_url=url,
            source_name=source_name,
            venue=source.get("venue"),
            city=source.get("city"),
            tz=source.get("tz", "America/New_York"),
            days_ahead=source.get("days_ahead", 90),
        )

    if not url:
        logger.warning("Source missing url: %s", source)
        return []

    if source_type == "rss":
        return fetch_rss(url, source_name, tz=source.get("tz", "America/New_York"))

    # HTML: fetch and return text + source for normalizer
    html = fetch_html(url)
    if not html:
        return []

    text = extract_text(html)
    if not text or len(text) < 50:
        logger.warning("Insufficient text extracted from %s", url)
        return []

    return {"text": text, "source": source}
