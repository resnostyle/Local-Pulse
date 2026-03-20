"""Local Pulse - Data ingestion service entry point."""

import argparse
import json
import logging
import time

from config import load_calendar_sources
from db.sources import ensure_tables, get_due_sources, get_enabled_sources, row_to_source_dict, sync_from_yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _filter_sources(sources: list[dict], only: list[str]) -> list[dict]:
    """Filter sources to those matching --only (by source name)."""
    if not only:
        return sources
    only_set = {s.strip().lower() for s in only if s.strip()}
    return [
        src
        for src in sources
        if src["name"].lower() in only_set
        or any(o in src["name"].lower() for o in only_set)
    ]


def _sync() -> None:
    """Ensure DB tables exist and sync YAML sources into the sources table."""
    ensure_tables()
    sync_from_yaml(load_calendar_sources())


def run_async(only: list[str] | None = None) -> int:
    """Dispatch scrape tasks to Celery workers."""
    from tasks import scrape_source

    _sync()
    sources = get_enabled_sources()
    sources = _filter_sources(sources, only or [])

    if not sources:
        logger.warning("No sources to run")
        return 0

    dispatched = 0
    for src in sources:
        scrape_source.delay(src["id"])
        dispatched += 1
        logger.info("Dispatched task for %s (id=%d)", src["name"], src["id"])

    logger.info("Dispatched %d tasks", dispatched)
    return dispatched


def run_inline(only: list[str] | None = None, force: bool = False) -> int:
    """Run pipeline inline (no Celery) for debugging and local dev."""
    from db import events as db_events
    from db.sources import record_run
    from normalizer import normalizer as norm
    from scraper import scraper as scrap

    _sync()

    if force:
        sources = get_enabled_sources()
    else:
        sources = get_due_sources()

    sources = _filter_sources(sources, only or [])

    if not sources:
        logger.warning("No sources due for scraping")
        return 0

    if only:
        logger.info("Running only: %s", [s["name"] for s in sources])

    total_inserted = 0
    for source_row in sources:
        source = row_to_source_dict(source_row)

        started = time.time()
        try:
            result = scrap.fetch_events_for_source(source)
            if result is None:
                duration_ms = int((time.time() - started) * 1000)
                record_run(source_id=source_row["id"], status="no_change", duration_ms=duration_ms)
                continue

            if isinstance(result, list):
                events = result
            elif isinstance(result, dict) and "text" in result:
                events = norm.normalize(result["text"], result["source"])
            else:
                events = []

            inserted = db_events.insert_events(events) if events else 0
            total_inserted += inserted
            duration_ms = int((time.time() - started) * 1000)

            record_run(
                source_id=source_row["id"],
                status="success" if events else "no_change",
                events_found=len(events),
                events_inserted=inserted,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - started) * 1000)
            record_run(
                source_id=source_row["id"],
                status="error",
                duration_ms=duration_ms,
                error_message=str(e)[:2000],
            )
            logger.exception("Failed to process %s: %s", source_row["name"], e)

    logger.info("Pipeline complete: %d events inserted/updated", total_inserted)
    return total_inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local Pulse ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run                          # Dispatch all enabled sources to Celery
  python main.py run --only espn              # Dispatch only ESPN
  python main.py run --inline                 # Run inline (no Celery, for debugging)
  python main.py run --inline --only espn     # Run ESPN inline
  python main.py run --inline --force         # Run all sources inline, ignore schedule
  python main.py sync                         # Sync YAML to DB without running
        """,
    )
    parser.add_argument(
        "command",
        choices=["run", "sync"],
        help="run = scrape sources; sync = sync YAML to DB only",
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="SOURCE",
        help="Run only these sources (by name). Can repeat.",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        dest="run_inline",
        help="Run inline without Celery (for debugging/local dev).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass schedule interval (only with --inline).",
    )
    args = parser.parse_args()

    if args.command == "sync":
        _sync()
        logger.info("YAML synced to sources table")
    elif args.command == "run":
        if args.run_inline:
            run_inline(only=args.only, force=args.force)
        else:
            run_async(only=args.only)


if __name__ == "__main__":
    main()
