locals {
  domain = cloudflare_zone.zebernst_dev.name
  zone   = cloudflare_zone.zebernst_dev.id

  # Fastmail DKIM selector CNAMEs (fm1/fm2/fm3).
  fastmail_dkim = {
    for i in range(1, 4) : "fm${i}" => {
      name    = "fm${i}._domainkey.${local.domain}"
      content = "fm${i}.${local.domain}.dkim.fmhosted.com"
    }
  }

  # Fastmail MX (apex + wildcard).
  mx = {
    apex_primary = {
      name     = local.domain
      content  = "in1-smtp.messagingengine.com"
      priority = 10
    }
    apex_secondary = {
      name     = local.domain
      content  = "in2-smtp.messagingengine.com"
      priority = 20
    }
    wildcard_primary = {
      name     = "*.${local.domain}"
      content  = "in1-smtp.messagingengine.com"
      priority = 10
    }
    wildcard_secondary = {
      name     = "*.${local.domain}"
      content  = "in2-smtp.messagingengine.com"
      priority = 20
    }
  }

}

resource "cloudflare_dns_record" "google_domainconnect" {
  comment = "Came with Google Domains"
  content = "connect.domains.google.com"
  name    = "_domainconnect.${local.domain}"
  proxied = false
  ttl     = 1
  type    = "CNAME"
  zone_id = local.zone
  settings = {
    flatten_cname = false
  }
}

resource "cloudflare_dns_record" "fastmail_dkim" {
  for_each = local.fastmail_dkim

  comment = "Fastmail"
  content = each.value.content
  name    = each.value.name
  proxied = false
  ttl     = 1
  type    = "CNAME"
  zone_id = local.zone
  settings = {
    flatten_cname = false
  }
}

resource "cloudflare_dns_record" "mx" {
  for_each = local.mx

  comment  = "Fastmail"
  content  = each.value.content
  name     = each.value.name
  priority = each.value.priority
  proxied  = false
  ttl      = 1
  type     = "MX"
  zone_id  = local.zone
}

resource "cloudflare_dns_record" "bsky_atproto" {
  comment = "BlueSky Social ATP Verification"
  content = "\"did=did:plc:pxo52v54v5pqxg4vm3m7ezcc\""
  name    = "_atproto.${local.domain}"
  proxied = false
  ttl     = 1
  type    = "TXT"
  zone_id = local.zone
}

resource "cloudflare_dns_record" "dkim_cloudflare" {
  content = "\"v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAiweykoi+o48IOGuP7GR3X0MOExCUDY/BCRHoWBnh3rChl7WhdyCxW3jgq1daEjPPqoi7sJvdg5hEQVsgVRQP4DcnQDVjGMbASQtrY4WmB1VebF+RPJB2ECPsEDTpeiI5ZyUAwJaVX7r6bznU67g7LvFq35yIo4sdlmtZGV+i0H4cpYH9+3JJ78k\" \"m4KXwaf9xUJCWF6nxeD+qG6Fyruw1Qlbds2r85U9dkNDVAS3gioCvELryh1TxKGiVTkg4wqHTyHfWsp7KD3WQHYJn0RyfJJu6YEmL77zonn7p2SRMvTMP3ZEXibnC9gz3nnhR6wcYL8Q7zXypKTMD58bTixDSJwIDAQAB\""
  name    = "cf2024-1._domainkey.${local.domain}"
  proxied = false
  ttl     = 1
  type    = "TXT"
  zone_id = local.zone
}

resource "cloudflare_dns_record" "dmarc" {
  content = "\"v=DMARC1; p=quarantine; rua=mailto:admin@${local.domain},mailto:8877933bd64d4f2c9bb00fff76d4aa45@dmarc-reports.cloudflare.net\""
  name    = "_dmarc.${local.domain}"
  proxied = false
  ttl     = 1
  type    = "TXT"
  zone_id = local.zone
}

resource "cloudflare_dns_record" "fastmail_spf" {
  comment = "Fastmail"
  content = "\"v=spf1 include:spf.messagingengine.com ?all\""
  name    = local.domain
  proxied = false
  ttl     = 1
  type    = "TXT"
  zone_id = local.zone
}
