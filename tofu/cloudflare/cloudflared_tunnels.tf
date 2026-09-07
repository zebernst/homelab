resource "cloudflare_zero_trust_tunnel_cloudflared" "cloudflared_noauth" {
  account_id = data.cloudflare_account.account.id
  config_src = "local"
  name       = "k8s"
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "cloudflared_auth" {
  account_id = data.cloudflare_account.account.id
  config_src = "local"
  name       = "k8s-auth"
}

