data "onepassword_vault" "secrets" {
  name = "Secrets"
}

resource "onepassword_item" "storage_box" {
  vault = data.onepassword_vault.secrets.uuid

  title    = "hcloud-storagebox"
  username = hcloud_storage_box.offsite.username
  url      = "sftp://${hcloud_storage_box.offsite.server}"
  password = var.storage_box_password

  tags = ["opentofu", "hetzner", "storage-box"]
}

resource "onepassword_item" "storage_box_synology" {
  vault = data.onepassword_vault.secrets.uuid

  title    = "hcloud-storagebox-user-synology"
  username = hcloud_storage_box_subaccount.synology.username
  url      = "smb://${hcloud_storage_box_subaccount.synology.server}"
  password = random_password.storage_box_synology.result

  tags = ["opentofu", "hetzner", "storage-box", "synology"]
}
