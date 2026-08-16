# Deployment — GitLab + R2 + CDN

## Architecture

```
GitLab scheduled pipeline (every 2–4h)
  → scrape + reduce → sync to Cloudflare R2
  → React app on GitLab Pages → fetches events JSON from CDN
```

Data layout under `LOCALPULSE_DATA_ROOT` (default `./data`):

| Path | Visibility | Purpose |
|------|------------|---------|
| `raw/{state}/{city}/{source}/{run_id}.json` | Private | Append-only scrape runs |
| `meta/sources/{name}.json` | Private | ETag, last run, backoff |
| `events/index.json` | Public | Location catalog |
| `events/locations/{state}/{city}/by-date/YYYY-MM-DD.json` | Public | Event lists |

## Local development

```bash
cp .env.example .env
cp python/config/calendars.yaml.example python/config/calendars.yaml
cd python && pip install -r requirements.txt

export LOCALPULSE_DATA_ROOT=../data
python main.py run --force   # scrape + reduce
python main.py reduce --all  # rebuild events/ from raw/
```

Or with Docker:

```bash
docker compose run --rm ingest
```

Serve events JSON locally (optional):

```bash
cd data && python -m http.server 8080
```

Frontend dev:

```bash
cd frontend && npm install && npm run dev
```

## Cloudflare R2

### Option A — GitLab CI + Terraform (recommended)

Push to `main` with changes under `terraform/` — the pipeline applies automatically. Secrets are read from Vault ([docs/VAULT.md](VAULT.md)).

### Option B — Terraform locally

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
export TF_VAR_cloudflare_api_token="..."
terraform init && terraform apply
```

See [terraform/README.md](../terraform/README.md).

### Option C — Manual dashboard

1. Create a bucket (e.g. `localpulse-data`).
2. Create R2 API token with read/write on that bucket.
3. Enable public access for the `events/` prefix **or** attach a custom domain.

GitLab CI/CD variables (non-secret — see [docs/VAULT.md](docs/VAULT.md) for Vault secrets):

| Variable | Example |
|----------|---------|
| `R2_ACCESS_KEY_ID` | (from R2 token) |
| `R2_SECRET_ACCESS_KEY` | (from R2 token) |
| `R2_BUCKET` | `localpulse-data` |
| `R2_ENDPOINT` | `https://<account_id>.r2.cloudflarestorage.com` |
| `OPENAI_API_KEY` | (only if using `html` sources) |

## GitLab schedule

1. **CI/CD → Schedules → New schedule**
2. Cron: `0 */3 * * *` (every 3 hours)
3. Target branch: default branch

The `ingest:pipeline` job runs on schedule: pulls `meta/` and `raw/` from R2, runs `python main.py run --force`, pushes all three prefixes back.

Manual ingest from the UI: run pipeline with variable `RUN_INGEST=true`.

## CDN URL for React

Set `VITE_EVENTS_BASE` at build time to your public events URL, e.g.:

```
https://events.yourdomain.com
```

The app requests `{VITE_EVENTS_BASE}/index.json` and `{VITE_EVENTS_BASE}/locations/{state}/{city}/by-date/{date}.json`.

Map your CDN origin to the R2 `events/` prefix.
