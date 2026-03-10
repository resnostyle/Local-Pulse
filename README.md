# Local Pulse

Aggregates local events from multiple websites so users do not need to search multiple calendars.

## Architecture

Two services share one MySQL database:

- **Python service** – scrapes event pages, normalizes data with AI, inserts into MySQL
- **Go service** – web server and API, renders pages with Go templates + HTMX

No direct communication between services; both read/write through the database.

## Prerequisites

- Python 3.11+
- Go 1.18+
- Docker (for MySQL)

## Quick Start

Using [mise](https://mise.jdx.dev/) (recommended):

```bash
mise run setup          # Copy .env, install deps
mise run db-init        # Start MySQL and load schema
mise run go             # Start web server (or `mise run python` for ingestion)
```

Manual setup:

1. Copy environment variables: `cp .env.example .env` (set `OPENAI_API_KEY` if using AI normalizer)
2. Start MySQL: `docker compose up -d`
3. Load schema: `mysql -h localhost -u localpulse -plocalpulse localpulse < schema/init.sql`
4. Run Python: `cd python && pip install -r requirements.txt && python main.py`
5. Run Go: `cd go && go run .`

The site will be available at http://localhost:8080

## Mise Tasks

| Task | Description |
|------|-------------|
| `mise run setup` | Copy .env, install Python and Go deps |
| `mise run db-up` | Start MySQL |
| `mise run db-down` | Stop MySQL |
| `mise run db-schema` | Load database schema |
| `mise run db-init` | Start MySQL and load schema |
| `mise run python` | Run Python ingestion service |
| `mise run python-install` | Install Python dependencies |
| `mise run go` | Run Go web server |
| `mise run go-build` | Build Go binary to `go/bin/server` |

## Project Structure

```text
├── python/          # Data ingestion (scraper, AI normalizer)
├── go/              # Web server (handlers, templates)
├── schema/          # Database schema
└── docker-compose.yml
```
