"""Configuration for the ingestion service."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LOCALPULSE_DATA_ROOT = os.getenv("LOCALPULSE_DATA_ROOT", "")


def load_calendar_sources() -> list[dict]:
    """Load calendar sources from calendars.yaml."""
    config_path = Path(__file__).parent / "calendars.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        data = yaml.safe_load(f)
    data = data or {}
    return data.get("calendars", [])
