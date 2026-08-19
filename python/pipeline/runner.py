"""Scrape one source: fetch, normalize, write raw, update meta."""

from __future__ import annotations

import logging
import time
from typing import Literal

from normalizer import normalizer as norm
from pipeline.meta import record_run_result
from pipeline.raw_writer import write_raw_run
from scraper import scraper as scrap

logger = logging.getLogger(__name__)

ScrapeStatus = Literal["success", "no_change", "error"]


def scrape_one_source(source: dict) -> ScrapeStatus:
    """Run fetch → normalize → raw write for one source dict. Returns status."""
    source_name = source.get("source", "unknown")
    started = time.time()

    try:
        result = scrap.fetch_events_for_source(source)
        if result is None:
            duration_ms = int((time.time() - started) * 1000)
            record_run_result(source_name, status="no_change", duration_ms=duration_ms)
            return "no_change"

        if isinstance(result, list):
            events = result
        elif isinstance(result, dict) and "text" in result:
            events = norm.normalize(result["text"], result["source"])
        else:
            events = []

        write_raw_run(source, events)
        duration_ms = int((time.time() - started) * 1000)
        status: ScrapeStatus = "success" if events else "no_change"
        record_run_result(
            source_name,
            status=status,
            events_found=len(events),
            duration_ms=duration_ms,
        )
        logger.info(
            "Source %s: %d events (%dms)",
            source_name,
            len(events),
            duration_ms,
        )
        return status

    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        record_run_result(
            source_name,
            status="error",
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        logger.exception("Source %s failed: %s", source_name, exc)
        return "error"
