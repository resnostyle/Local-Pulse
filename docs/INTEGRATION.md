# Integration Guide

This document describes the shared database contract between the **Python ingestion service** and the **Go web frontend**, and how the Celery worker system operates.

## Architecture

```
Celery Beat (scheduler)
        |
        | dispatches scrape_source tasks per source interval
        v
Redis (broker)  <-->  Celery Workers (1+)
                             |
                             | writes events + scrape_runs
                             v
                           MySQL
                             ^
                             | reads events
                             |
                        Go Server
```

Both services communicate only through MySQL. There is no direct service-to-service API.

## Database Tables

All timestamps are stored in **UTC**.

### `events`

The core data table. Both services interact with it.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INT | AUTO_INCREMENT, PK | Surrogate key |
| title | VARCHAR(500) | NOT NULL | Event title |
| description | TEXT | | Event description |
| start_time | DATETIME | NOT NULL | When the event starts (UTC) |
| end_time | DATETIME | | When the event ends (UTC) |
| venue | VARCHAR(255) | | Venue or location name |
| city | VARCHAR(100) | | City (used for filtering) |
| category | VARCHAR(100) | | Category (used for filtering) |
| source | VARCHAR(255) | | Human-readable source name |
| source_url | VARCHAR(1000) | | URL of the event or source page |
| recurring | TINYINT(1) | DEFAULT 0 | Whether the event repeats |
| fingerprint | VARCHAR(64) | NOT NULL, UNIQUE | Deduplication key |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Insert time |
| updated_at | TIMESTAMP | ON UPDATE CURRENT_TIMESTAMP | Last update time |

**Indexes:** `start_time`, `city`, `category`

### `sources`

Tracks registered data sources. Synced from `calendars.yaml` on startup.

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| name | VARCHAR(255) | Unique source name |
| source_type | VARCHAR(50) | Handler type (rss, ical, nmc_json, espn, html) |
| url | VARCHAR(1000) | Feed or page URL |
| config | JSON | Extra config fields from YAML (venue, city, tz, etc.) |
| schedule_interval_minutes | INT | How often to scrape (default 360) |
| retry_count | INT | Consecutive failures (reset on success) |
| max_retries | INT | Failures before auto-disable (default 5) |
| backoff_until | DATETIME | Don't retry before this time |
| enabled | TINYINT(1) | Whether the source is active |
| etag | VARCHAR(255) | HTTP ETag for conditional requests |
| last_modified | VARCHAR(255) | HTTP Last-Modified for conditional requests |

### `scrape_runs`

Audit log of every scrape attempt. One row per source per run.

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| source_id | INT | FK to sources.id |
| status | ENUM | success, error, skipped, no_change |
| events_found | INT | Events parsed from source |
| events_inserted | INT | Events inserted/updated in DB |
| duration_ms | INT | Wall time of the scrape |
| error_message | TEXT | Error details (on failure) |
| http_status | INT | HTTP response code (if applicable) |
| started_at | DATETIME | When the scrape began |
| finished_at | DATETIME | When the scrape completed |

**Useful queries:**

```sql
-- Failure rate per source
SELECT s.name, r.status, COUNT(*) as cnt
FROM scrape_runs r JOIN sources s ON r.source_id = s.id
GROUP BY s.name, r.status;

-- Sources with errors in the last 24 hours
SELECT s.name, r.error_message, r.started_at
FROM scrape_runs r JOIN sources s ON r.source_id = s.id
WHERE r.status = 'error' AND r.started_at > NOW() - INTERVAL 1 DAY;

-- Average scrape duration per source
SELECT s.name, AVG(r.duration_ms) as avg_ms
FROM scrape_runs r JOIN sources s ON r.source_id = s.id
WHERE r.status = 'success'
GROUP BY s.name;
```

## Fingerprint (Deduplication)

The `fingerprint` column prevents duplicate events. It is a SHA-256 hash (64 hex chars) computed from:

```
title + start_time + source_url
```

Python computes the fingerprint before insert and uses `ON DUPLICATE KEY UPDATE` to upsert when a fingerprint match exists. The Go service reads fingerprint but does not use it for logic.

## Retry and Backoff

When a Celery task fails:

1. Celery retries the task up to 5 times with exponential backoff (60s, 120s, 240s, ..., capped at 1 hour).
2. On persistent failure, `db/sources.py` increments `retry_count` and sets `backoff_until`.
3. After `max_retries` consecutive failures, the source is automatically disabled (`enabled = 0`).
4. On success, `retry_count` resets to 0 and `backoff_until` is cleared.

## Conditional Requests

For sources that support it, the fetcher stores HTTP `ETag` and `Last-Modified` headers in the `sources` table. On subsequent fetches, these are sent as `If-None-Match` / `If-Modified-Since` headers. A 304 response skips parsing entirely and records `no_change`.

## Python Service

**CLI commands:**

```bash
python main.py sync                       # Sync YAML to sources table
python main.py run                        # Dispatch all enabled sources to Celery
python main.py run --only "Source Name"   # Dispatch specific source
python main.py run --sync                 # Run inline (no Celery needed)
python main.py run --sync --force         # Run all sources inline, ignore schedule
```

**Celery processes:**

```bash
# Worker (executes tasks)
celery -A celery_app worker --loglevel=info --concurrency=4

# Beat (schedules tasks per source interval)
celery -A celery_app beat --loglevel=info --scheduler beat_schedule.DatabaseScheduler
```

**Source configuration:** `python/config/calendars.yaml`

Each entry requires `source` (unique name), `type`, and optionally `url` and `interval_minutes`. Additional fields like `venue`, `city`, `tz`, `base_url`, and `days_ahead` are stored in the `config` JSON column and passed through to handlers.

## Go Service

**Connects to MySQL** using `MYSQL_*` environment variables.

**Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /` | Index page |
| `GET /events` | All upcoming events |
| `GET /events/today` | Today's events |
| `GET /events/weekend` | Weekend events |
| `GET /events/category/:cat` | Events by category |
| `GET /health` | Health check |

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `MYSQL_HOST` | Both | MySQL host (default: localhost) |
| `MYSQL_PORT` | Both | MySQL port (default: 3306) |
| `MYSQL_USER` | Both | MySQL user |
| `MYSQL_PASSWORD` | Both | MySQL password |
| `MYSQL_DATABASE` | Both | Database name (default: localpulse) |
| `OPENAI_API_KEY` | Python | Required for `html` source type |
| `CELERY_BROKER_URL` | Python | Redis broker (default: redis://localhost:6379/0) |
| `CELERY_RESULT_BACKEND` | Python | Redis result backend (default: redis://localhost:6379/1) |
