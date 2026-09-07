locals {
  # https://docs.hetzner.cloud/reference/hetzner#storage-boxes-password-policy
  storage_box_password_specials = "!#$%*+-/=?@[]_{}"
}

resource "hcloud_storage_box" "offsite" {
  name             = "offsite"
  storage_box_type = "bx21"
  location         = "hel1"
  password         = var.storage_box_password

  access_settings = {
    reachable_externally = true
    ssh_enabled          = true
  }

  snapshot_plan = {
    max_snapshots = 20
    hour          = 12 # UTC
    minute        = 00
  }

  delete_protection = true

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [ssh_keys] # only populateable on create; replacement forces resource recreation and data loss.
  }
}

resource "hcloud_storage_box_subaccount" "synology" {
  storage_box_id = hcloud_storage_box.offsite.id
  description = "Synology HyperBackup"

  name           = "synology"
  home_directory = "backup/synology/"
  password       = random_password.storage_box_synology.result

  access_settings = {
    reachable_externally = true
    ssh_enabled          = true
  }
}

resource "random_password" "storage_box_synology" {
  length           = 40
  min_lower        = 1
  min_upper        = 1
  min_numeric      = 1
  min_special      = 1
  override_special = local.storage_box_password_specials
}