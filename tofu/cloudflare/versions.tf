terraform {
  required_version = ">= 1.8"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }

  backend "s3" {
    bucket = "jupiter-tofu-state"
    key    = "opentofu/cloudflare.tfstate"
    region = "us-west-001"

    endpoints = {
      s3 = "https://s3.us-west-001.backblazeb2.com"
    }

    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}

# Authenticated via CLOUDFLARE_API_TOKEN (fnox → 1Password).
provider "cloudflare" {}
