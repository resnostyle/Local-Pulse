variable "cloudflare_api_token" {
  description = "Cloudflare API token with R2 edit permissions (set via TF_VAR_cloudflare_api_token or -var)."
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID (Dashboard → R2 → right sidebar)."
  type        = string
}

variable "bucket_name" {
  description = "R2 bucket name for raw/, meta/, and events/ prefixes."
  type        = string
  default     = "localpulse-data"
}

variable "bucket_location" {
  description = "R2 bucket location hint (e.g. ENAM, WNAM, WEUR). Empty = automatic."
  type        = string
  default     = "ENAM"
}

variable "events_custom_domain" {
  description = "Custom domain for public events JSON (e.g. events.example.com). Leave empty to skip."
  type        = string
  default     = ""

  validation {
    condition     = var.events_custom_domain == "" || can(regex("^[a-z0-9.-]+$", var.events_custom_domain))
    error_message = "events_custom_domain must be a hostname without scheme or path."
  }
}

variable "cloudflare_zone_id" {
  description = "Zone ID for events_custom_domain (required when events_custom_domain is set)."
  type        = string
  default     = ""
}

variable "enable_r2_dev_domain" {
  description = "Enable Cloudflare-managed *.r2.dev public URL (useful for testing without a custom domain)."
  type        = bool
  default     = false
}

variable "cors_allowed_origins" {
  description = "Origins allowed to read events JSON from the browser (GitLab Pages URL, local dev, etc.)."
  type        = list(string)
  default     = ["*"]
}

variable "tags" {
  description = "Optional labels applied via bucket name prefix only (R2 has no native tags in TF)."
  type        = map(string)
  default     = {}
}
