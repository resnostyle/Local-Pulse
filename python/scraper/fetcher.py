"""Fetch HTML content from calendar URLs."""

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (compatible; LocalPulse/1.0; +https://github.com/localpulse)"
)


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
