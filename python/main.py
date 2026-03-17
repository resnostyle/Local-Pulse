"""Local Pulse - Data ingestion service entry point."""

import argparse
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import (
    RUN_MIN_INTERVAL_SECONDS,
    SCHEDULE_CRON,
    load_calendar_sources,
)
from db import events as db_events
from normalizer import normalizer as norm
from run_guard import endpoint_id, run_guard
from scraper import scraper as scrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _filter_sources(sources: list[dict], only: list[str]) -> list[dict]:
    """Filter sources to those matching --only (by source name or endpoint_id)."""
    if not only:
        return sources
    only_set = [s.strip().lower() for s in only if s.strip()]
    filtered = []
    for src in sources:
        name = (src.get("source") or "").lower()
        eid = endpoint_id(src).lower()
        if any(o in name or o in eid for o in only_set):
            filtered.append(src)
    return filtered


def run_pipeline(only: list[str] | None = None, force: bool = False) -> int:
    """Run the full ingestion pipeline: scrape, normalize, insert.

    Args:
        only: If set, run only these sources (by name or endpoint_id).
        force: If True, bypass rate limit (still uses mutex).
    """
    sources = load_calendar_sources()
    if not sources:
        logger.warning("No calendar sources configured")
        return 0

    sources = _filter_sources(sources, only or [])
    if not sources:
        logger.warning("No sources match --only %s", only)
        return 0
    if only:
        logger.info("Running only: %s", [s.get("source") or s.get("url", "?") for s in sources])

    total_inserted = 0
    for source in sources:
        with run_guard(
            source,
            min_interval_seconds=RUN_MIN_INTERVAL_SECONDS,
            force=force,
        ) as (ok, eid):
            if not ok:
                continue
            try:
                result = scrap.fetch_events_for_source(source)
                if isinstance(result, list):
                    events = result
                else:
                    events = norm.normalize(result["text"], result["source"])
                if events:
                    total_inserted += db_events.insert_events(events)
            except Exception as e:
                ident = source.get("url") or source.get("source", "?")
                logger.exception("Failed to process %s: %s", ident, e)

    logger.info("Pipeline complete: %d events inserted/updated", total_inserted)
    return total_inserted


def main() -> None:
    """CLI entry: run (one-shot) or schedule (weekly daemon)."""
    parser = argparse.ArgumentParser(
        description="Local Pulse ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                    # Run all sources (rate limited)
  python main.py run --only espn        # Run only ESPN
  python main.py run --only espn "Visit Raleigh"
  python main.py run --force            # Bypass rate limit
  python main.py schedule               # Run weekly via cron
        """,
    )
    parser.add_argument(
        "command",
        choices=["run", "schedule"],
        help="run = one-shot; schedule = weekly daemon",
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="SOURCE",
        help="Run only these sources (by name, e.g. ESPN or 'Visit Raleigh'). Can repeat.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass rate limit (min interval between runs). Mutex still applies.",
    )
    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(only=args.only, force=args.force)
    elif args.command == "schedule":
        # Parse SCHEDULE_CRON (e.g. "0 2 * * 0" = min hour day month weekday)
        parts = SCHEDULE_CRON.split()
        if len(parts) >= 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        else:
            trigger = CronTrigger(day_of_week="sun", hour=2, minute=0)
        scheduler = BlockingScheduler()
        scheduler.add_job(run_pipeline, trigger)
        logger.info("Scheduler started (cron=%s)", SCHEDULE_CRON)
        scheduler.start()


if __name__ == "__main__":
    main()
