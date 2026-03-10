"""Configuration for the ingestion service."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "localpulse")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "localpulse")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "localpulse")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Scheduler: default Sunday 2:00 AM UTC
SCHEDULE_CRON = os.getenv("SCHEDULE_CRON", "0 2 * * 0")


def load_calendar_sources() -> list[dict]:
    """Load calendar sources from calendars.yaml."""
    config_path = Path(__file__).parent / "calendars.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("calendars", [])
