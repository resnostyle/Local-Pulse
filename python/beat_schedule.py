"""Dynamic Celery Beat scheduler that reads source intervals from MySQL."""

import logging

from celery.beat import Scheduler, ScheduleEntry
from celery.schedules import schedule

logger = logging.getLogger(__name__)

DEFAULT_TICK_INTERVAL = 60  # check for due sources every 60 seconds


class DatabaseScheduler(Scheduler):
    """Beat scheduler that dispatches scrape_source tasks for due sources.

    Instead of maintaining a static schedule, this checks the sources table
    on each tick and enqueues tasks for any source that is due.
    """

    def __init__(self, *args, **kwargs):
        self._last_sync = 0
        super().__init__(*args, **kwargs)

    def setup_schedule(self):
        self.update_schedule(self.app)

    def update_schedule(self, app):
        """Sync YAML to DB and build schedule entries from enabled sources."""
        from config import load_calendar_sources
        from db.sources import ensure_tables, get_enabled_sources, sync_from_yaml

        ensure_tables()
        calendars = load_calendar_sources()
        sync_from_yaml(calendars)

        sources = get_enabled_sources()
        new_schedule = {}
        for src in sources:
            interval_seconds = src["schedule_interval_minutes"] * 60
            entry_name = f"scrape-{src['name']}"
            new_schedule[entry_name] = self.Entry(
                name=entry_name,
                task="tasks.scrape_source",
                schedule=schedule(run_every=interval_seconds),
                args=[src["id"]],
                app=self.app,
            )
        self.merge_inplace(new_schedule)
        logger.info("Beat schedule: %d sources", len(new_schedule))

    @property
    def schedule(self):
        return self.data

    @schedule.setter
    def schedule(self, value):
        self.data = value

    def tick(self):
        """Re-sync schedule from DB periodically (every 5 minutes)."""
        import time

        now = time.time()
        if now - self._last_sync > 300:
            self.update_schedule(self.app)
            self._last_sync = now
        return super().tick()
