# Local Pulse Integration Guide

This document describes the shared database contract between the **Python ingestion service** and the **Go web frontend**. Both services communicate only through MySQL; there is no direct service-to-service API.

## Architecture

```
Python Service (ingestion)          Go Service (web)
        |                                    |
        | writes events                      | reads events
        v                                    v
              MySQL (events table)
```

## Database Table: `events`

All timestamps are stored in **UTC**.

| Column       | Type         | Constraints | Description |
|-------------|--------------|-------------|-------------|
| id          | INT          | AUTO_INCREMENT, PRIMARY KEY | Surrogate key |
| title       | VARCHAR(500) | NOT NULL    | Event title |
| description | TEXT         |             | Event description (plain text) |
| start_time  | DATETIME     | NOT NULL    | When the event starts (UTC) |
| end_time    | DATETIME     |             | When the event ends (UTC); may be NULL |
| venue       | VARCHAR(255) |             | Venue or location name |
| city        | VARCHAR(100) |             | City (used for filtering) |
| category    | VARCHAR(100) |             | Category (e.g. Arts, Sports; used for filtering) |
| source      | VARCHAR(255) |             | Human-readable source name (e.g. "Visit Raleigh") |
| source_url  | VARCHAR(1000)|             | URL of the event or source page |
| fingerprint | VARCHAR(64) | NOT NULL, UNIQUE | Deduplication key (see below) |
| created_at  | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP | Insert time |
| updated_at  | TIMESTAMP    | ON UPDATE CURRENT_TIMESTAMP | Last update time |

### Fingerprint (Deduplication)

The `fingerprint` column prevents duplicate events. It is a SHA-256 hash (64 hex chars) of:

```
title + "|" + start_time_iso + "|" + source_url
```

- Python: Computes fingerprint before insert; uses `ON DUPLICATE KEY UPDATE` to upsert when fingerprint matches.
- Go: Reads fingerprint but does not use it for logic; it is an internal deduplication field.

### Indexes

- `idx_start_time (start_time)` – Used for date-range queries (today, weekend).
- `idx_city (city)` – Used for city filtering.
- `idx_category (category)` – Used for category filtering.

---

## Python Service (Ingestion)

**Purpose:** Scrape calendar websites, extract events via ChatGPT or RSS parsing, and insert into MySQL.

**Behavior:**

- Runs weekly (default: Sunday 2:00 AM UTC) or on-demand via `python main.py run`.
- Supports two source types:
  - **RSS:** Fetches RSS/Atom feeds, parses items, extracts dates from description.
  - **HTML:** Fetches HTML, extracts text, sends to ChatGPT for structured JSON extraction.
- Inserts events with `ON DUPLICATE KEY UPDATE` on fingerprint; duplicates are updated rather than duplicated.

**Config:** `python/config/calendars.yaml` lists sources with `url`, `source`, and `type` (rss or html).

---

## Go Service (Web Frontend)

**Purpose:** Serve the website and display events.

**Behavior:**

- Connects to MySQL using `MYSQL_*` env vars.
- Queries events via `go/db/events.go`:
  - `ListEvents` – All events, ordered by start_time.
  - `ListEventsToday` – Events starting today (UTC).
  - `ListEventsWeekend` – Events from Saturday 00:00 through Sunday 23:59 (UTC).
  - `ListEventsByCategory` – Events in a given category.

**Endpoints:**

- `GET /` – Index with all events.
- `GET /events` – All events.
- `GET /events/today` – Today’s events.
- `GET /events/weekend` – Weekend events.
- `GET /events/category/:category` – Events by category.

---

## Environment Variables

| Variable        | Used By | Description |
|-----------------|---------|-------------|
| MYSQL_HOST      | Both    | MySQL host (default: localhost) |
| MYSQL_PORT      | Both    | MySQL port (default: 3306) |
| MYSQL_USER      | Both    | MySQL user |
| MYSQL_PASSWORD  | Both    | MySQL password |
| MYSQL_DATABASE  | Both    | Database name (default: localpulse) |
| OPENAI_API_KEY  | Python  | Required for HTML sources (ChatGPT extraction) |
| SCHEDULE_CRON   | Python  | Cron expression for weekly run (default: `0 2 * * 0`) |

---

## Data Flow

1. Python runs the pipeline (scheduled or manual).
2. For each configured source:
   - **RSS:** Fetch feed → parse → map to events → insert.
   - **HTML:** Fetch page → extract text → ChatGPT → JSON events → insert.
3. Go serves HTTP requests and queries `events` for display.
4. Users see aggregated events from all sources.
