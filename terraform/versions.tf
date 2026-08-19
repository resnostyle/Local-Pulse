terraform {
  required_version = ">= 1.5.0"

  backend "http" {}

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

check "events_domain_requires_zone" {
  assert {
    condition     = var.events_custom_domain == "" || var.cloudflare_zone_id != ""
    error_message = "Set cloudflare_zone_id when events_custom_domain is configured."
  }
}
