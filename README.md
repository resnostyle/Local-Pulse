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

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `OPENAI_API_KEY` if using the AI normalizer.

2. Start MySQL:

   ```bash
   docker-compose up -d
   ```

3. Initialize the database schema:

   ```bash
   mysql -h localhost -u localpulse -plocalpulse localpulse < schema/init.sql
   ```

4. Start the Python service (ingestion):

   ```bash
   cd python && pip install -r requirements.txt && python main.py
   ```

5. Start the Go service (web):

   ```bash
   cd go && go run .
   ```

   The site will be available at http://localhost:8080

## Project Structure

```
├── python/          # Data ingestion (scraper, AI normalizer)
├── go/              # Web server (handlers, templates)
├── schema/          # Database schema
└── docker-compose.yml
```
