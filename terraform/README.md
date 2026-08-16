# Terraform — Cloudflare R2 for Local Pulse

Provisions the object storage and public events CDN used by the GitLab ingest pipeline.

## What this creates

| Resource | Purpose |
|----------|---------|
| `cloudflare_r2_bucket` | Single bucket for `raw/`, `meta/`, `events/` prefixes |
| `cloudflare_r2_custom_domain` | Public HTTPS for events JSON (optional) |
| `cloudflare_r2_managed_domain` | `*.r2.dev` URL for testing (optional) |
| `cloudflare_r2_bucket_cors` | Browser access from GitLab Pages / dev |

Terraform does **not** create R2 S3 API keys (Access Key ID / Secret). Create those once in the Cloudflare dashboard and store them as masked GitLab CI variables.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- Cloudflare account with R2 enabled
- API token with **Account → Workers R2 Storage → Edit**
- (Optional) Domain on Cloudflare for `events_custom_domain`

## GitLab CI (recommended for production)

Terraform runs in GitLab on changes to `terraform/`:

- **MR / main:** `validate` → `plan` (plan artifact)
- **main only:** `apply` (automatic, no manual gate)

Secrets come from **HashiCorp Vault** via GitLab ID tokens — see [docs/VAULT.md](../docs/VAULT.md).

State is stored in **GitLab** (Operate → Terraform states → `localpulse`).

After the first apply, copy `R2_BUCKET`, `R2_ENDPOINT`, and `VITE_EVENTS_BASE` from the job’s `terraform.env` dotenv artifact into GitLab CI/CD variables (or rely on the apply job output in the same pipeline).

## Local usage

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set cloudflare_account_id and optional domain

export TF_VAR_cloudflare_api_token="your-api-token"

terraform init
terraform plan
terraform apply
```

After apply:

```bash
terraform output gitlab_ci_variables
terraform output manual_steps
```

## GitLab CI variables

| Variable | Source |
|----------|--------|
| `R2_BUCKET` | `terraform output -raw bucket_name` |
| `R2_ENDPOINT` | `terraform output -raw r2_endpoint` |
| `R2_ACCESS_KEY_ID` | Manual — R2 API token |
| `R2_SECRET_ACCESS_KEY` | Manual — R2 API token |
| `VITE_EVENTS_BASE` | `terraform output -json gitlab_ci_variables` → `VITE_EVENTS_BASE` |

## URL layout

The ingest job syncs compiled JSON to `s3://$R2_BUCKET/events/`. With custom domain `events.example.com`:

```
https://events.example.com/events/index.json
https://events.example.com/events/locations/nc/raleigh/by-date/2026-06-11.json
```

Set `VITE_EVENTS_BASE=https://events.example.com/events` in the GitLab Pages build.

## Testing with r2.dev

For a throwaway environment:

```hcl
bucket_name          = "localpulse-dev"
enable_r2_dev_domain = true
```

Use the `r2_dev_domain` output as the public host. Do not use r2.dev for production buckets that also hold private `raw/` and `meta/` data — create a separate dev bucket or use a custom domain with path awareness.

## Destroy

```bash
terraform destroy
```

Empty the bucket first if destroy fails due to non-empty bucket.
