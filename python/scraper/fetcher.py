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
DEFAULT_CRAWL_DELAY = 0.3  # seconds when robots.txt has no Crawl-delay

# Crawl-delay is non-standard but widely used (e.g. Visit Raleigh)
CRAWL_DELAY_RE = re.compile(r"Crawl-delay:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Fetch raw HTML from a URL.

    Uses requests with a standard User-Agent. For JS-rendered pages,
    consider using Playwright instead.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML string or None on failure
    """
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def extract_text(html: str) -> str:
    """Extract visible text from HTML for AI processing."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def get_crawl_delay(url: str) -> float:
    """Fetch robots.txt for the URL's origin and return Crawl-delay in seconds.

    Crawl-delay is a non-standard directive used by some sites. Returns
    DEFAULT_CRAWL_DELAY if not found or on parse/fetch failure.

    Args:
        url: Any URL on the target site (e.g. https://example.com/page)

    Returns:
        Delay in seconds (>= 0.1, <= 60)
    """
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
