"""CRUD for sources and scrape_runs tables."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import pymysql

from config import MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER

logger = logging.getLogger(__name__)


def _conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_tables() -> None:
    """Create sources and scrape_runs tables if they don't exist."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  name VARCHAR(255) NOT NULL UNIQUE,
                  source_type VARCHAR(50) NOT NULL,
                  url VARCHAR(1000),
                  config JSON,
                  schedule_interval_minutes INT NOT NULL DEFAULT 360,
                  retry_count INT NOT NULL DEFAULT 0,
                  max_retries INT NOT NULL DEFAULT 5,
                  backoff_until DATETIME,
                  enabled TINYINT(1) DEFAULT 1,
                  etag VARCHAR(255),
                  last_modified VARCHAR(255),
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scrape_runs (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  source_id INT NOT NULL,
                  status ENUM('success','error','skipped','no_change') NOT NULL,
                  events_found INT DEFAULT 0,
                  events_inserted INT DEFAULT 0,
                  duration_ms INT,
                  error_message TEXT,
                  http_status INT,
                  started_at DATETIME NOT NULL,
                  finished_at DATETIME,
                  FOREIGN KEY (source_id) REFERENCES sources(id),
                  INDEX idx_source_status (source_id, status),
                  INDEX idx_started (started_at)
                )
            """)
        conn.commit()
    finally:
        conn.close()


def sync_from_yaml(calendars: list[dict]) -> None:
    """Upsert sources from calendars.yaml into the sources table.

    New entries are inserted, existing entries have url/type/config/interval updated.
    Sources removed from YAML are disabled (not deleted) to preserve history.
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM sources")
            existing = {row["name"]: row["id"] for row in cur.fetchall()}

            yaml_names = set()
            for cal in calendars:
                name = cal.get("source", "").strip()
                if not name:
                    continue
                yaml_names.add(name)

                source_type = cal.get("type", "html")
                url = cal.get("url", "")
                interval = cal.get("interval_minutes", 360)
                extra = {
                    k: v
                    for k, v in cal.items()
                    if k not in ("source", "type", "url", "interval_minutes")
                }
                config_json = json.dumps(extra) if extra else None

                if name in existing:
                    cur.execute(
                        """UPDATE sources
                           SET source_type = %s, url = %s, config = %s,
                               schedule_interval_minutes = %s, enabled = 1,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE name = %s""",
                        (source_type, url, config_json, interval, name),
                    )
                else:
                    cur.execute(
                        """INSERT INTO sources
                           (name, source_type, url, config, schedule_interval_minutes)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (name, source_type, url, config_json, interval),
                    )

            removed = set(existing.keys()) - yaml_names
            for name in removed:
                cur.execute(
                    "UPDATE sources SET enabled = 0 WHERE name = %s",
                    (name,),
                )

        conn.commit()
        logger.info(
            "Synced %d sources from YAML (%d disabled)",
            len(yaml_names),
            len(removed),
        )
    finally:
        conn.close()


def get_source(source_id: int) -> Optional[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sources WHERE id = %s", (source_id,))
            return cur.fetchone()
    finally:
        conn.close()


def get_source_by_name(name: str) -> Optional[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sources WHERE name = %s", (name,))
            return cur.fetchone()
    finally:
        conn.close()


def get_enabled_sources() -> list[dict]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sources WHERE enabled = 1 ORDER BY name"
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_due_sources() -> list[dict]:
    """Return enabled sources that are due for a scrape run.

    A source is due if:
    - It has never run, OR
    - Its last run was longer ago than schedule_interval_minutes, AND
    - It is not in backoff (backoff_until is NULL or in the past)
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.*,
                       MAX(r.started_at) AS last_run_at
                FROM sources s
                LEFT JOIN scrape_runs r ON r.source_id = s.id
                WHERE s.enabled = 1
                  AND (s.backoff_until IS NULL OR s.backoff_until <= UTC_TIMESTAMP())
                GROUP BY s.id
                HAVING last_run_at IS NULL
                    OR TIMESTAMPDIFF(MINUTE, last_run_at, UTC_TIMESTAMP()) >= s.schedule_interval_minutes
            """)
            return cur.fetchall()
    finally:
        conn.close()


def record_run(
    source_id: int,
    status: str,
    events_found: int = 0,
    events_inserted: int = 0,
    duration_ms: int = 0,
    error_message: Optional[str] = None,
    http_status: Optional[int] = None,
) -> None:
    """Record a scrape run and update source retry state."""
    now = datetime.utcnow()
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scrape_runs
                   (source_id, status, events_found, events_inserted,
                    duration_ms, error_message, http_status, started_at, finished_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    source_id,
                    status,
                    events_found,
                    events_inserted,
                    duration_ms,
                    error_message,
                    http_status,
                    now - timedelta(milliseconds=duration_ms),
                    now,
                ),
            )

            if status in ("success", "no_change"):
                cur.execute(
                    "UPDATE sources SET retry_count = 0, backoff_until = NULL WHERE id = %s",
                    (source_id,),
                )
            elif status == "error":
                cur.execute("SELECT retry_count, max_retries FROM sources WHERE id = %s", (source_id,))
                row = cur.fetchone()
                if row:
                    new_count = row["retry_count"] + 1
                    if new_count >= row["max_retries"]:
                        cur.execute(
                            "UPDATE sources SET retry_count = %s, enabled = 0 WHERE id = %s",
                            (new_count, source_id),
                        )
                        logger.warning(
                            "Source %s disabled after %d consecutive failures",
                            source_id,
                            new_count,
                        )
                    else:
                        backoff_seconds = min(60 * (2 ** new_count), 86400)
                        backoff_until = now + timedelta(seconds=backoff_seconds)
                        cur.execute(
                            "UPDATE sources SET retry_count = %s, backoff_until = %s WHERE id = %s",
                            (new_count, backoff_until, source_id),
                        )

        conn.commit()
    finally:
        conn.close()


def get_fetch_metadata(source_id: int) -> Optional[dict]:
    """Get stored ETag/Last-Modified for a source."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT etag, last_modified FROM sources WHERE id = %s",
                (source_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def set_fetch_metadata(
    source_id: int,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> None:
    """Store ETag/Last-Modified after a successful fetch."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            updates = []
            params = []
            if etag is not None:
                updates.append("etag = %s")
                params.append(etag)
            if last_modified is not None:
                updates.append("last_modified = %s")
                params.append(last_modified)
            if updates:
                params.append(source_id)
                cur.execute(
                    f"UPDATE sources SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
        conn.commit()
    finally:
        conn.close()
