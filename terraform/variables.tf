variable "tailscale_oauth_client_id" {
  description = "Tailscale OAuth client ID for Terraform"
  type        = string
  sensitive   = true
}

variable "tailscale_oauth_client_secret" {
  description = "Tailscale OAuth client secret for Terraform"
  type        = string
  sensitive   = true
}

variable "tailnet" {
  description = "Tailscale tailnet name"
  type        = string
  default     = "kite-harmonic.ts.net"
}

variable "udm_pro_ip" {
  description = "UDM Pro IP used as DNS nameserver for internal domains"
  type        = string
  default     = "192.168.1.1"
}
