"""Fetch HTML content from calendar URLs."""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"
)
DEFAULT_CRAWL_DELAY = 0.3

CRAWL_DELAY_RE = re.compile(r"Crawl-delay:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def fetch_with_conditional(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    user_agent: str = USER_AGENT,
    source_id: Optional[int] = None,
) -> Optional[str]:
    """Fetch URL with HTTP conditional request (ETag/Last-Modified).

    If source_id is provided, reads/writes ETag and Last-Modified from the
    sources table. Otherwise falls back to a plain GET.

    Returns response body as str, or None if 304 or on error.
    """
    headers = {"User-Agent": user_agent}

    if source_id is not None:
        try:
            from db.sources import get_fetch_metadata

            stored = get_fetch_metadata(source_id)
            if stored:
                if stored.get("etag"):
                    headers["If-None-Match"] = stored["etag"]
                if stored.get("last_modified"):
                    headers["If-Modified-Since"] = stored["last_modified"]
        except Exception as e:
            logger.debug("Could not load fetch metadata for source %s: %s", source_id, e)

    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        if resp.status_code == 304:
            logger.info("Skipping %s: not modified (304)", url)
            return None
        resp.raise_for_status()

        if source_id is not None:
            etag = resp.headers.get("ETag")
            last_modified = resp.headers.get("Last-Modified")
            if etag or last_modified:
                try:
                    from db.sources import set_fetch_metadata

                    set_fetch_metadata(source_id, etag, last_modified)
                except Exception as e:
                    logger.debug("Could not save fetch metadata: %s", e)

        return resp.text
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT, source_id: Optional[int] = None) -> Optional[str]:
    """Fetch raw HTML from a URL.

    Uses conditional fetch (ETag/Last-Modified) when source_id is provided.
    """
    return fetch_with_conditional(url, timeout=timeout, user_agent=USER_AGENT, source_id=source_id)


def extract_text(html: str) -> str:
    """Extract visible text from HTML for AI processing."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def get_crawl_delay(url: str) -> float:
    """Fetch robots.txt for the URL's origin and return Crawl-delay in seconds."""
    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(origin + "/", "robots.txt")
        resp = requests.get(
            robots_url,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        match = CRAWL_DELAY_RE.search(resp.text)
        if match:
            delay = float(match.group(1))
            return max(0.1, min(60.0, delay))
    except (requests.RequestException, ValueError) as e:
        logger.debug("Could not get Crawl-delay from robots.txt: %s", e)
    return DEFAULT_CRAWL_DELAY
