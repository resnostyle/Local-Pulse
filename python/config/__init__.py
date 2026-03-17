"""Configuration for the ingestion service."""

import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
_raw_port = os.getenv("MYSQL_PORT", "3306")
try:
    MYSQL_PORT = int(_raw_port)
except (ValueError, TypeError):
    logger.warning("Invalid MYSQL_PORT %r, using default 3306", _raw_port)
    MYSQL_PORT = 3306
MYSQL_USER = os.getenv("MYSQL_USER", "localpulse")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "localpulse")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "localpulse")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Scheduler: default Sunday 2:00 AM UTC
SCHEDULE_CRON = os.getenv("SCHEDULE_CRON", "0 2 * * 0")

# Run guard: min minutes between runs per endpoint (avoid abusing servers)
_raw_interval = os.getenv("RUN_MIN_INTERVAL_MINUTES", "60")
try:
    RUN_MIN_INTERVAL_MINUTES = max(1, int(_raw_interval))
except (ValueError, TypeError):
    logger.warning(
        "Invalid RUN_MIN_INTERVAL_MINUTES %r; using default 60",
        _raw_interval,
    )
    RUN_MIN_INTERVAL_MINUTES = 60
RUN_MIN_INTERVAL_SECONDS = RUN_MIN_INTERVAL_MINUTES * 60


def load_calendar_sources() -> list[dict]:
    """Load calendar sources from calendars.yaml."""
    config_path = Path(__file__).parent / "calendars.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        data = yaml.safe_load(f)
    data = data or {}
    return data.get("calendars", [])
