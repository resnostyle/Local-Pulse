"""AI-powered normalization of scraped event text into structured JSON."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI

from .prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


def normalize(text: str, source: dict) -> list[dict]:
    """Extract events from text using ChatGPT and return event dicts.

    Args:
        text: Raw text extracted from calendar page
        source: Dict with url, source

    Returns:
        List of event dicts with keys: title, description, start_time, end_time,
        venue, city, category, source, source_url
    """
    from config import OPENAI_API_KEY

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; skipping AI normalization")
        return []

    source_name = source.get("source", "Unknown")
    source_url = source.get("url", "")

    user_prompt = build_user_prompt(text, source_name, source_url)

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content
    except Exception as e:
        logger.warning("OpenAI API error: %s", e)
        return []

    if content is None:
        logger.warning("OpenAI returned empty content")
        return []

    # Parse JSON (handle markdown code blocks)
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw_events = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse OpenAI response as JSON: %s", e)
        return []

    if not isinstance(raw_events, list):
        return []

    events = []
    for item in raw_events:
        if not isinstance(item, dict) or "title" not in item:
            continue
        evt = _normalize_event(item, source_name, source_url)
        if evt:
            events.append(evt)

    logger.info("Normalized %d events from %s", len(events), source_url)
    return events


def _normalize_event(item: dict, source_name: str, source_url: str) -> Optional[dict]:
    """Convert raw AI output to our schema."""
    title = item.get("title")
    if not title or not isinstance(title, str):
        return None

    start_str = item.get("start_time")
    if not start_str:
        return None
    start_time = _parse_iso(start_str)
    if not start_time:
        return None

    end_str = item.get("end_time")
    end_time = _parse_iso(end_str) if end_str else None

    desc = item.get("description")
    description = str(desc)[:5000] if desc else None

    def _str(v) -> Optional[str]:
        return str(v).strip() or None if v is not None else None

    recurring = bool(item.get("recurring"))
    return {
        "title": title.strip(),
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "venue": _str(item.get("venue")),
        "city": _str(item.get("city")),
        "category": _str(item.get("category")),
        "source": source_name,
        "source_url": source_url,
        "recurring": recurring,
    }


def _parse_iso(s: str) -> Optional[datetime]:
    """Parse ISO 8601 string to naive UTC datetime."""
    if not s:
        return None
    s = str(s).strip()
    # Normalize Z to +00:00 for strptime
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            parse_s = s[:10] if fmt == "%Y-%m-%d" else s
            dt = datetime.strptime(parse_s, fmt)
            if hasattr(dt, "tzinfo") and dt.tzinfo:
                offset = dt.utcoffset() or timedelta(0)
                dt = (dt.replace(tzinfo=None) - offset)
            return dt
        except ValueError:
            continue
    return None
