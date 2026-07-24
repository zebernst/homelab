resource "tailscale_dns_preferences" "main" {
  magic_dns = true
}

# Global fallback nameservers for domains not covered by split DNS
resource "tailscale_dns_nameservers" "main" {
  nameservers = [
    "1.1.1.1",
    "1.0.0.1",
  ]
}

# Split DNS: route internal domain queries to UDM Pro dnsmasq,
# which holds records synced by ExternalDNS
resource "tailscale_dns_split_nameservers" "zebernst_dev" {
  domain      = "zebernst.dev"
  nameservers = [var.udm_pro_ip]
}

resource "tailscale_dns_split_nameservers" "internal" {
  domain      = "internal"
  nameservers = [var.udm_pro_ip]
}

resource "tailscale_dns_search_paths" "main" {
  search_paths = ["internal"]
}
