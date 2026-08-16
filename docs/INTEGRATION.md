# Integration Guide

This document describes the JSON file contract between the **Python ingestion pipeline** and the **React frontend**.

## Architecture

```
calendars.yaml
      |
      v
Python scrapers (GitLab CI or local)
      |
      +--> data/raw/           append-only scrape runs
      +--> data/meta/sources/  per-source schedule + HTTP cache state
      +--> data/events/        compiled public JSON
      |
      v
Cloudflare R2 + CDN  <-----  React (GitLab Pages)
```

There is no database. The React app reads static JSON over HTTP.

## Data directories

All paths are relative to `LOCALPULSE_DATA_ROOT` (default `./data`).

### Raw runs — `raw/{state}/{city}/{source}/{run_id}.json`

Private, append-only. One file per scrape attempt.

```json
{
  "run_at": "2026-04-03T12:30:45Z",
  "source": "Example Feed",
  "records": [
    {
      "title": "Concert",
      "start_time": "2026-03-15T19:00:00Z",
      "source_url": "https://example.com/e/1",
      "raw_hash": "abc..."
    }
  ]
}
```

### Source meta — `meta/sources/{slug}.json`

Tracks scheduling and conditional HTTP headers (ETag / Last-Modified).

### Public events — `events/`

| File | Purpose |
|------|---------|
| `events/index.json` | List of `{state, city}` locations with event counts |
| `events/locations/{state}/{city}/by-date/YYYY-MM-DD.json` | Events for one day |
| `events/locations/{state}/{city}/by-id/{id}.json` | Optional single-event lookup |

Compiled event objects include normalized fields (`title`, `description`, `start_time`, `end_time`, `venue`, `city`, `category`, `source`, `source_url`, `id`).

Dedupe logic lives in `python/pipeline/dedupe.py` (`processed_event_id`).

## CLI

```bash
cd python
python main.py run              # scrape due sources + reduce
python main.py run --force      # scrape all sources, ignore intervals
python main.py run --no-reduce  # scrape only
python main.py run --only "My Feed"
python main.py reduce --all
python main.py reduce --state nc --city raleigh
```

## Frontend

The React app (`frontend/`) expects:

- `GET {VITE_EVENTS_BASE}/index.json`
- `GET {VITE_EVENTS_BASE}/locations/{state}/{city}/by-date/{YYYY-MM-DD}.json`

Set `VITE_EVENTS_BASE` at build time to the CDN URL serving the `events/` prefix.

## Environment variables

| Variable | Description |
|----------|-------------|
| `LOCALPULSE_DATA_ROOT` | Root data directory (default `./data`) |
| `OPENAI_API_KEY` | Required for `html` source type |
| `R2_ACCESS_KEY_ID` | R2 sync (GitLab CI) |
| `R2_SECRET_ACCESS_KEY` | R2 sync (GitLab CI) |
| `R2_BUCKET` | Target bucket name |
| `R2_ENDPOINT` | S3-compatible endpoint URL |

## Adding sources

Edit `python/config/calendars.yaml`. Each entry needs at least `source`, `type`, and usually `url`. Set `state` and `city` slugs so the reducer can place events in the correct public paths.

Per-source scrape intervals use `interval_minutes` (default 360). State is persisted in `meta/sources/` — no separate sync step.
