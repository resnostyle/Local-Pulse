output "bucket_name" {
  description = "R2 bucket name — set as GitLab CI variable R2_BUCKET."
  value       = cloudflare_r2_bucket.data.name
}

output "r2_endpoint" {
  description = "S3-compatible endpoint — set as GitLab CI variable R2_ENDPOINT."
  value       = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}

output "events_base_url" {
  description = "Base URL for VITE_EVENTS_BASE (includes /events path prefix from CI sync)."
  value = (
    var.events_custom_domain != "" ? "https://${var.events_custom_domain}/events" :
    var.enable_r2_dev_domain ? "https://${cloudflare_r2_managed_domain.dev[0].domain}/events" :
    null
  )
}

output "events_custom_domain_status" {
  description = "Custom domain provisioning status (SSL + ownership)."
  value = var.events_custom_domain != "" ? {
    domain    = cloudflare_r2_custom_domain.events[0].domain
    ownership = try(cloudflare_r2_custom_domain.events[0].status.ownership, null)
    ssl       = try(cloudflare_r2_custom_domain.events[0].status.ssl, null)
  } : null
}

output "r2_dev_domain" {
  description = "Public r2.dev hostname when enable_r2_dev_domain is true."
  value       = var.enable_r2_dev_domain ? cloudflare_r2_managed_domain.dev[0].domain : null
}

output "gitlab_ci_variables" {
  description = "Non-secret GitLab CI/CD variables to configure after apply."
  value = {
    R2_BUCKET    = cloudflare_r2_bucket.data.name
    R2_ENDPOINT  = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
    VITE_EVENTS_BASE = (
      var.events_custom_domain != "" ? "https://${var.events_custom_domain}/events" :
      var.enable_r2_dev_domain ? "https://${cloudflare_r2_managed_domain.dev[0].domain}/events" :
      "/events"
    )
  }
}

output "manual_steps" {
  description = "Steps Terraform cannot automate yet."
  value       = <<-EOT
    1. Create an R2 S3 API token (Dashboard → R2 → Manage R2 API Tokens).
       Scope: Object Read & Write on bucket "${cloudflare_r2_bucket.data.name}".
       Set GitLab CI variables R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY (masked).
    2. Set GitLab CI variables R2_BUCKET and R2_ENDPOINT from terraform outputs.
    3. Set VITE_EVENTS_BASE in GitLab CI (or .gitlab-ci.yml) from events_base_url output.
    4. Add GitLab pipeline schedule: 0 */3 * * *
  EOT
}
