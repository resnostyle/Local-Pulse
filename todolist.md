# Local Pulse — Task List

**Target:** GitLab Runners + Cloudflare R2 + CDN + React  
**Deploy:** [docs/DEPLOY.md](docs/DEPLOY.md)

---

## Done

- [x] **Raw JSON writer after each scrape**
- [x] **`LOCALPULSE_DATA_ROOT` layout** (`data/raw/`, `data/meta/`, `data/events/`)
- [x] **`meta/sources/*.json`** — etag, last_run, backoff (`pipeline/meta.py`)
- [x] **`pipeline/dedupe.py`** — title+start+venue / source+url fallback
- [x] **`pipeline/reducer.py`** + `main.py reduce --all`
- [x] **YAML-driven `main.py run`** (JSON-only CLI)
- [x] **Tests** — dedupe, meta, reducer, fingerprint, raw_writer
- [x] **`.gitlab-ci.yml`** — test, scheduled ingest + R2 sync, Pages
- [x] **React frontend** (`frontend/`) — location + date picker
- [x] **Terraform** for R2 + GitLab auto-apply on main
- [x] **Removed MySQL / Celery / Redis** — no migration (app never deployed)

---

## Manual setup (you)

- [ ] Create Cloudflare R2 bucket + API token
- [ ] Configure Vault paths for Terraform + ingest ([docs/VAULT.md](docs/VAULT.md))
- [ ] Set GitLab CI/CD variables (`R2_*`, `OPENAI_API_KEY`)
- [ ] Add GitLab pipeline schedule (`0 */3 * * *`)
- [ ] Configure CDN custom domain for `events/` JSON
- [ ] Set `VITE_EVENTS_BASE` in GitLab Pages build to CDN URL

---

## Optional / later

- [ ] `meta/runs/` audit JSON for scrape history

---

## Decisions locked in

- JSON is the event datastore; public paths: `events/locations/{state}/{city}/by-date/…`
- Batch via **GitLab scheduled pipeline** + **R2** persistence between runs
- No MySQL, Celery, or Redis in the deployment path
