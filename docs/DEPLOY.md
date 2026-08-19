# Deployment — GitLab + Cloudflare + GitLab Pages

## Architecture

```
GitLab scheduled pipeline (every 3h)
  → scrape due sources + reduce → sync to Cloudflare R2

Cloudflare CDN (user-facing edge)
  ├── localpulse.com        → GitLab Pages (React SPA)
  └── events.localpulse.com → R2 (compiled events JSON)
```

| Role | Service | What it does |
|------|---------|--------------|
| **Workers** | GitLab scheduled pipeline | Scrape, reduce, sync `raw/`, `meta/`, `events/` to R2 |
| **Site origin** | GitLab Pages | Hosts the built React static files |
| **CDN / edge** | Cloudflare | Proxied in front of both the app domain and events subdomain |

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

## 1. Cloudflare R2 (storage)

### Option A — GitLab CI + Terraform (recommended)

Push to `main` with changes under `terraform/` — the pipeline applies automatically. Secrets are read from Vault ([docs/VAULT.md](VAULT.md)).

Set in GitLab CI/CD variables:

| Variable | Example |
|----------|---------|
| `TF_VAR_cloudflare_account_id` | Cloudflare account ID |
| `TF_VAR_events_custom_domain` | `events.localpulse.com` |
| `TF_VAR_cloudflare_zone_id` | Zone ID for your domain |

After first apply, copy from `terraform output`:

| Variable | Example |
|----------|---------|
| `R2_BUCKET` | `localpulse-data` |
| `R2_ENDPOINT` | `https://<account_id>.r2.cloudflarestorage.com` |
| `VITE_EVENTS_BASE` | `https://events.localpulse.com/events` |

Create an R2 S3 API token (Object Read & Write on the bucket) and store credentials in Vault — see [docs/VAULT.md](VAULT.md).

### Option B — Terraform locally

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
export TF_VAR_cloudflare_api_token="..."
terraform init && terraform apply
```

See [terraform/README.md](../terraform/README.md).

## 2. Cloudflare CDN (edge)

Both the app and events JSON are served through Cloudflare (orange-cloud proxied DNS records).

### App domain → GitLab Pages

1. Merge to `main` — the `pages` job builds React and publishes to GitLab Pages.
2. **Deploy → Pages** — note the GitLab Pages URL (e.g. `namespace.gitlab.io/project`).
3. **Deploy → Pages → New domain** — add your app domain (e.g. `localpulse.com`).
4. In **Cloudflare DNS** for your zone:
   - CNAME `localpulse.com` → GitLab Pages hostname (from step 2)
   - **Proxy status: Proxied** (orange cloud)
5. Cloudflare SSL/TLS mode: **Full** (GitLab provides a valid cert for the Pages hostname).

### Events subdomain → R2

Terraform creates the R2 custom domain binding when `TF_VAR_events_custom_domain` is set. Cloudflare DNS for the events subdomain is managed automatically by the R2 custom domain resource.

Ensure the record is **proxied**. Public URLs:

```
https://events.localpulse.com/events/index.json
https://events.localpulse.com/events/locations/nc/raleigh/by-date/2026-06-11.json
```

Set `VITE_EVENTS_BASE=https://events.localpulse.com/events` in GitLab CI/CD variables before the next Pages build.

## 3. GitLab pipeline schedule

1. **CI/CD → Schedules → New schedule**
2. Cron: `0 */3 * * *` (every 3 hours)
3. Target branch: default branch

The `ingest:pipeline` job:
- Pulls `meta/` and `raw/` from R2
- Runs `python main.py run` (scrapes **due** sources only, then reduces)
- Pushes `meta/`, `raw/`, and `events/` back to R2

Manual ingest: run pipeline with `RUN_INGEST=true`.

Force all sources (ignore intervals): add `RUN_INGEST_FORCE=true`.

## 4. Source configuration

Commit your sources in `python/config/calendars.yaml` (copy from `calendars.yaml.example`). The CI job falls back to the example file if none is committed.

## GitLab CI/CD variables summary

Non-secret (Settings → CI/CD → Variables):

| Variable | Required | Notes |
|----------|----------|-------|
| `VAULT_ADDR` | Yes | Vault server URL |
| `TF_VAR_cloudflare_account_id` | Yes | For Terraform |
| `TF_VAR_events_custom_domain` | Recommended | e.g. `events.localpulse.com` |
| `TF_VAR_cloudflare_zone_id` | If custom domain | Cloudflare zone ID |
| `R2_BUCKET` | After apply | From terraform output |
| `R2_ENDPOINT` | After apply | From terraform output |
| `VITE_EVENTS_BASE` | For Pages build | e.g. `https://events.localpulse.com/events` |

Secrets via Vault — see [docs/VAULT.md](VAULT.md):

- `OPENAI_API_KEY` (only if using `html` sources)
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
- `TF_VAR_cloudflare_api_token` (Terraform jobs)

## Validate end-to-end

1. Pipeline schedule runs → R2 bucket has `events/index.json`
2. `https://localpulse.com` loads the React app (via Cloudflare → GitLab Pages)
3. App fetches locations and events from `https://events.localpulse.com/events/...`
