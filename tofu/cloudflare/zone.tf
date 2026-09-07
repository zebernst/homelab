resource "cloudflare_zone" "zebernst_dev" {
  name                = "zebernst.dev"
  type                = "full"
  account = {
    id   = data.cloudflare_account.account.id
  }
}

