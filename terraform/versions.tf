terraform {
  required_version = ">= 1.5"

  required_providers {
    tailscale = {
      source  = "tailscale/tailscale"
      version = "~> 0.29"
    }
  }

  # Uncomment to persist state to Backblaze B2
  # backend "s3" {
  #   bucket                      = "<bucket-name>"
  #   key                         = "terraform/tailscale.tfstate"
  #   region                      = "us-west-004"
  #   endpoint                    = "https://s3.us-west-004.backblazeb2.com"
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   skip_region_validation      = true
  #   force_path_style            = true
  # }
}
