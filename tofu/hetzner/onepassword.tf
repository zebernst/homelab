data "onepassword_vault" "secrets" {
  name = "Secrets" # must match ../fnox.toml providers.op.vault
}

# Username/URL from Hetzner; passwords from var (primary) / random_password (synology).
# No cycle: password sources do not depend on these items.
# https://search.opentofu.org/provider/1password/onepassword/latest/docs/resources/item
#
# Do not set `category`: provider v3.3.1 resource schema omits api_credential
# (data source / real items still use it). https://github.com/1Password/terraform-provider-onepassword/issues/391

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
