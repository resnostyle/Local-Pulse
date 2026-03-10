"""Local Pulse - Data ingestion service entry point."""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SCHEDULE_CRON, load_calendar_sources
from db import events as db_events
from normalizer import normalizer as norm
from scraper import scraper as scrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline() -> int:
    """Run the full ingestion pipeline: scrape, normalize, insert."""
    sources = load_calendar_sources()
    if not sources:
        logger.warning("No calendar sources configured")
        return 0

    total_inserted = 0
    for source in sources:
        try:
            result = scrap.fetch_events_for_source(source)
            if isinstance(result, list):
                # RSS: result is list of events
                events = result
            else:
                # HTML: result is {text, source} for normalizer
                events = norm.normalize(result["text"], result["source"])
            if events:
                total_inserted += db_events.insert_events(events)
        except Exception as e:
            logger.exception("Failed to process %s: %s", source.get("url", "?"), e)

    logger.info("Pipeline complete: %d events inserted/updated", total_inserted)
    return total_inserted


def main() -> None:
    """CLI entry: run (one-shot) or schedule (weekly daemon)."""
    if len(sys.argv) < 2:
        print("Usage: python main.py run | schedule")
        print("  run      - Run ingestion once")
        print("  schedule - Run weekly (default: Sunday 2:00 AM UTC)")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "run":
        run_pipeline()
    elif cmd == "schedule":
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
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
