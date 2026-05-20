resource "tailscale_tailnet_settings" "main" {
  # Provision HTTPS certs for tailnet devices (needed for tailscale-unifi HTTPS)
  https_enabled = true

  # Prevent console edits since ACL is managed here
  acls_externally_managed_on = true

  # Devices don't auto-expire keys; control expiry manually
  devices_key_duration_days = 180
}

resource "tailscale_contacts" "main" {
  account {
    email = "zach.bernstein@fastmail.com"
  }

  support {
    email = "zach.bernstein@fastmail.com"
  }

  security {
    email = "zach.bernstein@fastmail.com"
  }
}
