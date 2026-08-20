# HashiCorp Vault + GitLab CI for Local Pulse

GitLab pipelines fetch secrets from Vault using **ID tokens** (OIDC). No secrets are stored in GitLab CI/CD variables except non-sensitive config (account IDs, Vault paths, `VAULT_ADDR`).

## Overview

| Job | Vault secrets |
|-----|----------------|
| `terraform:validate` / `plan` / `apply` | `TF_VAR_cloudflare_api_token` |
| `ingest:pipeline` | `OPENAI_API_KEY`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |

Terraform state is stored in **GitLab** (HTTP backend), not in Vault.

## 1. Enable GitLab ↔ Vault integration

In GitLab (**Settings → CI/CD → Vault**):

1. Set **Vault server URL** → `VAULT_ADDR` (e.g. `https://vault.example.com`)
2. Configure JWT auth path (often `jwt` or `gitlab`)

In Vault, create a JWT auth role bound to this project and branch, for example:

```hcl
# Example — adjust paths/policies for your org
resource "vault_jwt_auth_backend_role" "gitlab_localpulse" {
  backend   = vault_jwt_auth_backend.gitlab.path
  role_name = "localpulse"
  role_type = "jwt"

  user_claim       = "user_email"
  token_policies   = ["localpulse-ci"]

  bound_audiences = [var.vault_addr]
  bound_claims = {
    project_id = var.gitlab_project_id
    ref_type   = "branch"
    ref        = "main"
  }
}
```

For merge request pipelines, add a separate role or extend `bound_claims` with `ref_type = "merge_request_event"` and restrict policies to read-only secrets if needed.

## 2. Store secrets in Vault (KV v2)

Suggested paths under mount `secret`:

| Vault path | Field | Used as |
|------------|-------|---------|
| `localpulse/terraform/cloudflare_api_token` | value | `TF_VAR_cloudflare_api_token` |
| `localpulse/r2/access_key_id` | value | `R2_ACCESS_KEY_ID` |
| `localpulse/r2/secret_access_key` | value | `R2_SECRET_ACCESS_KEY` |
| `localpulse/openai/api_key` | value | `OPENAI_API_KEY` |

CLI example:

```bash
vault kv put secret/localpulse/terraform/cloudflare_api_token value="YOUR_CF_API_TOKEN"
vault kv put secret/localpulse/r2/access_key_id value="..."
vault kv put secret/localpulse/r2/secret_access_key value="..."
vault kv put secret/localpulse/openai/api_key value="..."
```

GitLab `secrets:` path format: `{path}/{field}@{mount}` → e.g. `localpulse/terraform/cloudflare_api_token@secret`

## 3. GitLab CI/CD variables (non-secret)

Set in **Settings → CI/CD → Variables**:

| Variable | Example | Notes |
|----------|---------|--------|
| `VAULT_ADDR` | `https://vault.example.com` | Must match JWT `aud` / Vault role `bound_audiences` |
| `TF_VAR_cloudflare_account_id` | `abc123...` | Cloudflare account ID |
| `TF_VAR_events_custom_domain` | `events.example.com` | Optional |
| `TF_VAR_cloudflare_zone_id` | `zone-id` | Required if custom domain set |
| `R2_BUCKET` | `localpulse-data` | From `terraform output` after first apply |
| `R2_ENDPOINT` | `https://<account>.r2.cloudflarestorage.com` | From terraform output |
| `VITE_EVENTS_BASE` | `https://events.example.com/events` | From terraform output |

Path overrides (defaults in `.gitlab-ci.yml`):

- `VAULT_TERRAFORM_CLOUDFLARE_TOKEN_PATH`
- `VAULT_OPENAI_API_KEY_PATH`
- `VAULT_R2_ACCESS_KEY_ID_PATH`
- `VAULT_R2_SECRET_ACCESS_KEY_PATH`

## 4. Vault policy (example)

```hcl
path "secret/data/localpulse/*" {
  capabilities = ["read"]
}
```

Scope policies per environment (`localpulse/staging/*` vs `localpulse/production/*`) using separate JWT roles.

## 5. Pipeline behaviour

```
push / MR
  test:python (+ test:frontend when frontend/ changes)
  terraform validate/plan/apply (when terraform/ changes)
  terraform:dotenv (main push only → R2_BUCKET, R2_ENDPOINT, VITE_EVENTS_BASE)
  pages (main push only → GitLab Pages build)

schedule (0 */3 * * *)
  ingest:pipeline only (Vault R2 + OpenAI secrets)

web (manual)
  RUN_INGEST=true  → ingest:pipeline
  RUN_INGEST_FORCE=true → scrape all sources, ignore intervals
```

**Apply is automatic on the default branch** when Terraform files change. There is no manual approval gate.

To add approval for production, add `when: manual` to `terraform:apply` or use protected environments.

## 6. Terraform state in GitLab

State name: `localpulse` (HTTP backend via `CI_JOB_TOKEN`).

View: **Operate → Terraform states** in the GitLab project.

Requires Maintainer role for state access; CI job token handles lock/unlock during jobs.

## 7. Local Terraform (optional)

Local runs still use `terraform.tfvars` + `TF_VAR_cloudflare_api_token`. For remote state locally:

```bash
export TF_HTTP_ADDRESS="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/terraform/state/localpulse"
export TF_HTTP_USERNAME="your-gitlab-username"
export TF_HTTP_PASSWORD="your-personal-access-token"
# ... other TF_HTTP_* vars
cd terraform && terraform init
```

Prefer running plan/apply via GitLab on main for production.

## Troubleshooting

| Error | Fix |
|-------|-----|
| Vault authentication failed | Check `VAULT_ADDR`, JWT role `bound_audiences`, and GitLab Vault integration |
| Secret not found | Verify KV path and field name match `secrets.vault` in `.gitlab/ci/*.yml` |
| State lock | Wait for job to finish or unlock in GitLab Terraform states UI |
| Apply skipped on main | No changes under `terraform/` — push a Terraform change or run pipeline manually |
