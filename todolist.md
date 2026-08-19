# Local Pulse — Task List

**Target:** GitLab pipeline + GitLab Pages + Cloudflare CDN + R2  
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
- [x] **Deployment docs** — GitLab workers, GitLab Pages origin, Cloudflare CDN edge

---

## Manual setup (you)

- [ ] Terraform apply → R2 bucket + `events.yourdomain.com`
- [ ] Configure Vault paths for Terraform + ingest ([docs/VAULT.md](docs/VAULT.md))
- [ ] Set GitLab CI/CD variables (`R2_*`, `VITE_EVENTS_BASE`, `TF_VAR_*`)
- [ ] Commit `python/config/calendars.yaml` with your sources
- [ ] Add GitLab pipeline schedule (`0 */3 * * *`)
- [ ] Cloudflare DNS: proxy app domain → GitLab Pages ([docs/DEPLOY.md](docs/DEPLOY.md))
- [ ] Verify events subdomain is proxied to R2

---

## Optional / later

- [ ] `meta/runs/` audit JSON for scrape history
- [ ] Same-origin `/events/*` via Cloudflare Worker (eliminates CORS)
- [ ] GitLab matrix fan-out for per-source parallel scrape (before Lambda)

---

## Decisions locked in

- JSON is the event datastore; public paths: `events/locations/{state}/{city}/by-date/…`
- **Workers:** GitLab scheduled pipeline + R2 persistence between runs
- **Site origin:** GitLab Pages (React SPA)
- **CDN edge:** Cloudflare proxied in front of Pages + R2 events domain
- No MySQL, Celery, Redis, or Lambda in v1
