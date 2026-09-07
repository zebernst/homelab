resource "cloudflare_zone_dnssec" "zebernst_dev_dnssec" {
  status  = "active"
  zone_id = cloudflare_zone.zebernst_dev.id
}

