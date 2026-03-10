"""Orchestrate scraping from calendar sources."""

import logging
from typing import Union

from .fetcher import extract_text, fetch_html
from .rss_handler import fetch_and_parse as fetch_rss

logger = logging.getLogger(__name__)


def fetch_events_for_source(source: dict) -> Union[list[dict], dict]:
    """Fetch and parse events from a single calendar source.

    Args:
        source: Dict with url, source, type (rss or html)

    Returns:
        For type=rss: list of event dicts (ready to insert).
        For type=html: dict with "text" and "source" for the normalizer to process.
    """
    url = source.get("url", "")
    source_name = source.get("source", "Unknown")
    source_type = source.get("type", "html")

    if not url:
        logger.warning("Source missing url: %s", source)
        return []

    if source_type == "rss":
        return fetch_rss(url, source_name)

    # HTML: fetch and return text + source for normalizer
    html = fetch_html(url)
    if not html:
        return []

    text = extract_text(html)
    if not text or len(text) < 50:
        logger.warning("Insufficient text extracted from %s", url)
        return []

    return {"text": text, "source": source}
