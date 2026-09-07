terraform {
  required_version = ">= 1.8"

  required_providers {
    b2 = {
      source  = "Backblaze/b2"
      version = "~> 0.13"
    }
  }

  backend "s3" {
    bucket = "jupiter-tofu-state"
    key    = "opentofu/b2.tfstate"
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

provider "b2" {}
