"""Celery tasks for scraping sources."""

import logging
import time

from celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True)
def scrape_source(self, source_id: int):
    """Scrape a single source end-to-end: fetch, normalize, insert, record.

    Retry is handled at the source level: record_run(status="error") updates
    retry_count and backoff_until on the source row, and Beat/get_due_sources
    skips the source until backoff expires.  This avoids conflicting with
    Celery's own retry mechanism.
    """
    from db import events as db_events
    from db.sources import get_source, record_run, row_to_source_dict
    from normalizer import normalizer as norm
    from scraper import scraper as scrap

    source_row = get_source(source_id)
    if not source_row or not source_row["enabled"]:
        return {"status": "skipped", "reason": "disabled or missing"}

    source = row_to_source_dict(source_row)
    source_name = source_row["name"]
    started = time.time()

    try:
        result = scrap.fetch_events_for_source(source)

        if result is None:
            duration_ms = int((time.time() - started) * 1000)
            record_run(
                source_id=source_id,
                status="no_change",
                duration_ms=duration_ms,
            )
            return {"status": "no_change", "source": source_name}

        if isinstance(result, list):
            events = result
        elif isinstance(result, dict) and "text" in result:
            events = norm.normalize(result["text"], result["source"])
        else:
            events = []

        inserted = db_events.insert_events(events) if events else 0
        duration_ms = int((time.time() - started) * 1000)

        status = "success" if events else "no_change"
        record_run(
            source_id=source_id,
            status=status,
            events_found=len(events),
            events_inserted=inserted,
            duration_ms=duration_ms,
        )
        logger.info(
            "Source %s: %d events found, %d inserted (%dms)",
            source_name,
            len(events),
            inserted,
            duration_ms,
        )
        return {
            "status": status,
            "source": source_name,
            "events_found": len(events),
            "inserted": inserted,
        }

    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        record_run(
            source_id=source_id,
            status="error",
            duration_ms=duration_ms,
            error_message=str(exc)[:2000],
        )
        logger.exception("Source %s failed: %s", source_name, exc)
        return {"status": "error", "source": source_name, "error": str(exc)[:200]}
