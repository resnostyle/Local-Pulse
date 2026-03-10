"""Insert events into MySQL with deduplication."""

import logging
from datetime import datetime
from typing import Optional

import pymysql

from config import MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER
from db.fingerprint import compute_fingerprint

logger = logging.getLogger(__name__)

INSERT_SQL = """
INSERT INTO events (
    title, description, start_time, end_time, venue, city, category,
    source, source_url, fingerprint
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    description = VALUES(description),
    end_time = VALUES(end_time),
    venue = VALUES(venue),
    city = VALUES(city),
    category = VALUES(category),
    updated_at = CURRENT_TIMESTAMP
"""


def _conn():
    """Create a pymysql connection."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
    )


def _format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime for MySQL (naive UTC)."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def insert_events(events: list[dict]) -> int:
    """Insert events into the database. Uses ON DUPLICATE KEY UPDATE for fingerprint.

    Args:
        events: List of event dicts with title, start_time, source_url, and optional
                description, end_time, venue, city, category, source

    Returns:
        Number of rows affected (inserted or updated).
    """
    if not events:
        return 0

    conn = _conn()
    try:
        inserted = 0
        with conn.cursor() as cur:
            for evt in events:
                title = evt.get("title", "")
                start_time = evt.get("start_time")
                source_url = evt.get("source_url", "")

                if not title or not start_time:
                    logger.warning("Skipping event missing title or start_time")
                    continue

                start_str = _format_datetime(start_time) if isinstance(start_time, datetime) else str(start_time)
                fingerprint = compute_fingerprint(title, start_str, source_url)

                row = (
                    title,
                    evt.get("description"),
                    start_time,
                    evt.get("end_time"),
                    evt.get("venue"),
                    evt.get("city"),
                    evt.get("category"),
                    evt.get("source"),
                    source_url,
                    fingerprint,
                )
                try:
                    cur.execute(INSERT_SQL, row)
                    inserted += cur.rowcount
                except pymysql.Error as e:
                    logger.warning("Insert failed for %s: %s", title, e)
        conn.commit()
        logger.info("Inserted/updated %d events", inserted)
        return inserted
    finally:
        conn.close()
