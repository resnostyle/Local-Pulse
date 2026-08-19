resource "cloudflare_r2_bucket" "data" {
  account_id = var.cloudflare_account_id
  name       = var.bucket_name
  location   = var.bucket_location
}

# Public read for events JSON via custom domain (production).
resource "cloudflare_r2_custom_domain" "events" {
  count = var.events_custom_domain != "" ? 1 : 0

  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.data.name
  domain      = var.events_custom_domain
  zone_id     = var.cloudflare_zone_id
  enabled     = true
  min_tls     = "1.2"
}

# Optional r2.dev URL for testing (exposes entire bucket — use a dev bucket name).
resource "cloudflare_r2_managed_domain" "dev" {
  count = var.enable_r2_dev_domain ? 1 : 0

  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.data.name
  enabled     = true
}

resource "cloudflare_r2_bucket_cors" "data" {
  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.data.name

  rules = [{
    allowed = {
      origins = var.cors_allowed_origins
      methods = ["GET", "HEAD"]
      headers = ["*"]
    }
    id              = "AllowEventsRead"
    max_age_seconds = 3600
  }]
}
