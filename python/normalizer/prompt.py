"""Build prompts for ChatGPT event extraction."""

SYSTEM_PROMPT = """You extract calendar/event items from web page text and return them as JSON.

Output a JSON array of objects. Each object must have these fields:
- title (string, required)
- description (string, optional)
- start_time (ISO 8601 UTC, e.g. "2026-03-15T14:00:00Z", required)
- end_time (ISO 8601 UTC, optional)
- venue (string, optional)
- city (string, optional)
- category (string, optional)
- recurring (boolean, optional): true if the event repeats (e.g. weekly, monthly)

Return ONLY valid JSON. No markdown, no explanation. If no events found, return []."""

USER_PROMPT_TEMPLATE = """Extract all calendar events from this text. Return a JSON array of event objects.

Source: {source}
Source URL: {source_url}

Text:
---
{text}
---
"""


def build_user_prompt(text: str, source: str, source_url: str) -> str:
    """Build the user prompt for event extraction."""
    return USER_PROMPT_TEMPLATE.format(
        source=source,
        source_url=source_url,
        text=text[:15000],  # Limit token usage
    )
