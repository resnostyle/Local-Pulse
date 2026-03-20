# Local Pulse

Aggregates local events from multiple websites into a single browsable calendar. Users see one unified view instead of checking dozens of separate sites.

## How It Works

Sources are defined in a YAML config file. Each source has a type (RSS, iCal, JSON API, HTML, or sports API) and a scrape interval. Celery workers process each source independently on its own schedule -- fetching data, normalizing it into a common event format, and inserting it into MySQL with fingerprint-based deduplication. A Go web server reads from the same database and serves the site using server-rendered HTML with HTMX for dynamic filtering.

The two services (Python ingestion, Go web) share a database and have no direct communication.

## Architecture

```
                          calendars.yaml
                               |
                               v
                        +--------------+
                        | Celery Beat  |  (scheduler)
                        +--------------+
                               |
                          dispatches tasks
                               |
                               v
  +-------+           +----------------+           +-------+
  | Redis | <-------> | Celery Workers | --------> | MySQL |
  +-------+  broker   +----------------+  insert   +-------+
                        |  |  |  |                      ^
                   rss ical json html+AI                |
                                                   reads events
                                                        |
                                                +-------+-------+
                                                |   Go Server   |
                                                | templates+HTMX|
                                                +---------------+
                                                        |
                                                     browser
```

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
│   ├── main.py                 # CLI entrypoint (run, sync)
│   ├── celery_app.py           # Celery app instance
│   ├── celery_config.py        # Broker/backend configuration
│   ├── tasks.py                # scrape_source task definition
│   ├── beat_schedule.py        # Dynamic Beat scheduler (reads sources table)
│   ├── config/
│   │   ├── __init__.py              # Env vars and YAML loader
│   │   ├── calendars.yaml.example   # Source definitions template
│   │   └── espn.yaml.example        # Sports API config template
│   ├── scraper/
│   │   ├── scraper.py          # Source router (dispatches to handlers)
│   │   ├── fetcher.py          # HTTP fetching with conditional requests
│   │   ├── rss_handler.py      # RSS/Atom feed parser
│   │   ├── ical_handler.py     # iCal (.ics) parser
│   │   ├── nmc_json_handler.py # WordPress JSON API parser
│   │   └── espn_handler.py     # Sports scoreboard API
│   ├── normalizer/
│   │   ├── normalizer.py       # LLM-based event extraction
│   │   └── prompt.py           # System/user prompts for the LLM
│   ├── db/
│   │   ├── events.py           # Event insert with deduplication
│   │   ├── sources.py          # Source and scrape run CRUD
│   │   └── fingerprint.py      # SHA-256 deduplication key
│   └── tests/                  # Unit tests
├── go/                         # Web server
│   ├── main.go                 # HTTP server entrypoint
│   ├── handlers/               # Route handlers
│   ├── db/                     # Database queries
│   ├── models/                 # Event model
│   ├── templates/              # Go HTML templates
│   └── static/                 # CSS
├── schema/
│   ├── init.sql                # Full database schema
│   └── migrations/             # Incremental migrations
├── helm/local-pulse/           # Helm chart for Kubernetes
├── docker-compose.yml          # Local dev (MySQL, Redis, workers)
├── Dockerfile.python           # Python service image
├── Dockerfile.go               # Go service image
└── mise.toml                   # Task runner config
```

## Database

Three tables in MySQL (all timestamps UTC):

- **`events`** -- the core data. Title, description, start/end time, venue, city, category, source, and a unique `fingerprint` for deduplication. Inserts use `ON DUPLICATE KEY UPDATE` so re-scraping the same event updates it instead of creating duplicates.
- **`sources`** -- registered data sources synced from `calendars.yaml`. Tracks schedule interval, retry count, backoff state, and conditional request metadata (ETag/Last-Modified).
- **`scrape_runs`** -- audit log of every scrape attempt. Records status, event counts, duration, and errors. Useful for identifying broken sources and tracking performance.

Schema lives in `schema/init.sql` and is also created automatically by the Python service on startup via `db/sources.py`.

## Adding a Source

Add an entry to `python/config/calendars.yaml`:

```yaml
calendars:
  - url: https://example.com/events/feed
    source: "Example Events"
    type: rss
    interval_minutes: 360
```

Fields:
- `source` -- human-readable name (must be unique)
- `type` -- one of `rss`, `ical`, `nmc_json`, `espn`, `html`
- `url` -- feed or page URL (not needed for `espn`)
- `interval_minutes` -- how often to scrape (default 360)
- Additional fields depending on type: `venue`, `city`, `tz`, `base_url`, `days_ahead`

On next startup or Beat tick, the source is synced to the `sources` table and begins running on schedule.

## Prerequisites

- Python 3.11+
- Go 1.21+
- Docker (for MySQL and Redis)

## Quick Start

Using [mise](https://mise.jdx.dev/):

```bash
mise run setup          # Copy .env and config files, install deps
mise run db-init        # Start MySQL + Redis, load schema
mise run python         # Run one-shot ingestion (or start worker/beat below)
mise run go             # Start web server
```

To run continuous ingestion instead, start the Celery worker and beat in separate terminals (see Manual setup below).

Manual setup:

```bash
# 1. Environment and config
cp .env.example .env                                       # Set OPENAI_API_KEY if using html sources
cp python/config/calendars.yaml.example python/config/calendars.yaml  # Add your sources
cp python/config/espn.yaml.example python/config/espn.yaml            # Configure sports region

# 2. Infrastructure
docker compose up -d    # MySQL + Redis

# 3. Schema
mysql -h localhost -u localpulse -plocalpulse localpulse < schema/init.sql

# 4. Python ingestion (pick one)
cd python && pip install -r requirements.txt

python main.py sync                     # Sync YAML sources to DB
python main.py run --inline               # Run all due sources inline
python main.py run --inline --only "ESPN" # Run one source inline
python main.py run                      # Dispatch to Celery workers

# Or start the full Celery stack:
celery -A celery_app worker --loglevel=info --concurrency=4  # in one terminal
celery -A celery_app beat --loglevel=info --scheduler beat_schedule.DatabaseScheduler  # in another

# 5. Go web server
cd go && go run .
```

The site will be available at http://localhost:8080.

## Running Tests

```bash
cd python && python -m pytest tests/ -v
cd go && go test ./...
```

## Deployment

A Helm chart is provided in `helm/local-pulse/` for Kubernetes deployment. It deploys:

- Go web server (Deployment + Service + optional Ingress)
- Celery worker (Deployment, scalable replicas)
- Celery beat (Deployment, single replica)
- Redis (Deployment + Service)

MySQL is expected to be deployed separately. Provide connection details via `values.yaml`:

```bash
helm install local-pulse ./helm/local-pulse \
  --set mysql.host=your-mysql-host \
  --set mysql.username=localpulse \
  --set mysqlPassword=your-password \
  --set image.go.repository=ghcr.io/your-org \
  --set image.python.repository=ghcr.io/your-org
```

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `MYSQL_HOST` | Both | MySQL host (default: localhost) |
| `MYSQL_PORT` | Both | MySQL port (default: 3306) |
| `MYSQL_USER` | Both | MySQL user |
| `MYSQL_PASSWORD` | Both | MySQL password |
| `MYSQL_DATABASE` | Both | Database name (default: localpulse) |
| `OPENAI_API_KEY` | Python | Required for `html` source type |
| `CELERY_BROKER_URL` | Python | Redis broker URL (default: redis://localhost:6379/0) |
| `CELERY_RESULT_BACKEND` | Python | Redis result backend (default: redis://localhost:6379/1) |

## Mise Tasks

| Task | Description |
|------|-------------|
| `mise run setup` | Copy .env, install Python and Go deps |
| `mise run db-up` | Start MySQL and Redis via Docker Compose |
| `mise run db-down` | Stop containers |
| `mise run db-schema` | Load database schema |
| `mise run db-init` | Start containers and load schema |
| `mise run python` | Run Python ingestion (one-shot) |
| `mise run python-test` | Run Python unit tests |
| `mise run go` | Run Go web server |
| `mise run go-build` | Build Go binary |
