resource "cloudflare_ruleset" "cache_bypass" {
  kind    = "zone"
  name    = "default"
  phase   = "http_request_cache_settings"
  zone_id = cloudflare_zone.zebernst_dev.id
  rules = [
    {
      action = "set_cache_settings"
      action_parameters = { cache = false }
      expression   = "(http.host eq \"plex.${cloudflare_zone.zebernst_dev.name}\")"
      description  = "Disable Cloudflare caching for Plex streaming traffic"
      ref          = "plex_bypass_cache"
    }, 
    {
      action = "set_cache_settings"
      action_parameters = { cache = false }
      expression   = "(http.host eq \"s3.${cloudflare_zone.zebernst_dev.name}\")"
      description  = "Disable Cloudflare caching for object storage endpoints"
      ref          = "s3_bypass_cache"
    }
  ]
}

