# Local Pulse

Aggregates local events from multiple websites into a single browsable calendar. Users see one unified view instead of checking dozens of separate sites.

## How It Works

Sources are defined in `python/config/calendars.yaml`. A scheduled **GitLab pipeline** runs every few hours: Python scrapers fetch each source, append **raw JSON** runs, a **reducer** rebuilds public **events JSON**, and the files sync to **Cloudflare R2**. A **React** app is hosted on **GitLab Pages** and served to users through **Cloudflare CDN**, which also fronts the events JSON subdomain.

```
calendars.yaml
      |
      v
GitLab scheduled job (every 3h)
      |
      +--> scrape --> data/raw/...        (private, append-only)
      +--> meta   --> data/meta/sources/  (ETag, schedule state)
      +--> reduce --> data/events/...     (public compiled JSON)
      |
      v
Cloudflare R2 (events subdomain)
      ^
      | fetch JSON
Cloudflare CDN ──> GitLab Pages (React SPA)
```

See [docs/DEPLOY.md](docs/DEPLOY.md) for R2, GitLab schedules, and local dev. See [docs/INTEGRATION.md](docs/INTEGRATION.md) for the JSON file contract.

## Source Types

| Type | How it works |
|------|-------------|
| `rss` | Fetches RSS/Atom feeds, parses items, extracts dates from descriptions. Enriches with times from detail pages when available. |
| `ical` | Fetches `.ics` feeds and parses VEVENT components. |
| `nmc_json` | Queries WordPress NMC-style JSON event APIs with date range parameters. |
| `espn` | Queries public sports scoreboard APIs and filters by configured region/teams. |
| `html` | Fetches a web page, extracts visible text, sends it to an LLM (GPT-4o-mini) to produce structured event JSON. |

New source types can be added by creating a handler in `python/scraper/` and registering it in `scraper.py`.

## Project Structure

```
local-pulse/
├── python/                     # Data ingestion service
│   ├── main.py                 # CLI (run, reduce)
│   ├── pipeline/               # JSON pipeline (raw, meta, reducer, dedupe)
│   ├── config/                 # calendars.yaml, env
│   ├── scraper/                # Source handlers
│   ├── normalizer/             # LLM extraction for html sources
│   └── tests/
├── frontend/                   # React SPA (GitLab Pages)
├── terraform/                  # Cloudflare R2 (GitLab CI apply on main)
├── docker-compose.yml          # Optional local ingest container
├── Dockerfile.python
└── mise.toml
```

## Adding a Source

Add an entry to `python/config/calendars.yaml`:

```yaml
calendars:
  - url: https://example.com/events/feed
    source: "Example Events"
    type: rss
    state: nc
    city: raleigh
    interval_minutes: 360
```

Fields:
- `source` — human-readable name (must be unique)
- `type` — one of `rss`, `ical`, `nmc_json`, `espn`, `html`
- `url` — feed or page URL (not needed for `espn`)
- `state`, `city` — slugs for compiled JSON paths (recommended)
- `interval_minutes` — how often to scrape (default 360)
- Additional fields depending on type: `venue`, `tz`, `base_url`, `days_ahead`

Schedule state (last run, ETag, backoff) is stored in `data/meta/sources/{name}.json`.

## Prerequisites

- Python 3.11+
- Node.js 20+ (frontend dev only)

## Quick Start

Using [mise](https://mise.jdx.dev/):

```bash
mise run setup
mise run python -- --force          # scrape all sources + reduce
cd frontend && npm install && npm run dev
```

Manual setup:

```bash
cp .env.example .env
cp python/config/calendars.yaml.example python/config/calendars.yaml

cd python && pip install -r requirements.txt
export LOCALPULSE_DATA_ROOT=../data
python main.py run --force
python main.py reduce --all
```

Serve compiled JSON locally:

```bash
cd data && python -m http.server 8080
```

## Running Tests

```bash
cd python && python -m pytest tests/ -v
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LOCALPULSE_DATA_ROOT` | Data directory (default: `./data`) |
| `OPENAI_API_KEY` | Required for `html` source type |
| `R2_*` | Cloudflare R2 credentials (GitLab CI ingest job) |

## Mise Tasks

| Task | Description |
|------|-------------|
| `mise run setup` | Copy .env, install Python deps |
| `mise run python` | Scrape due sources + reduce |
| `mise run ingest` | Same as python with `--force` |
| `mise run ingest-docker` | Run ingest via Docker Compose |
| `mise run python-test` | Run Python unit tests |
