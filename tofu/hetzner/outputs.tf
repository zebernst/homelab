output "storage_box" {
  description = "Primary Storage Box and nested subaccounts."
  value = {
    id       = hcloud_storage_box.offsite.id
    name     = hcloud_storage_box.offsite.name
    server   = hcloud_storage_box.offsite.server
    system   = hcloud_storage_box.offsite.system
    username = hcloud_storage_box.offsite.username
    location = hcloud_storage_box.offsite.location
    type     = hcloud_storage_box.offsite.storage_box_type

    subaccounts = {
      synology = {
        id             = hcloud_storage_box_subaccount.synology.id
        name           = hcloud_storage_box_subaccount.synology.name
        username       = hcloud_storage_box_subaccount.synology.username
        server         = hcloud_storage_box_subaccount.synology.server
        home_directory = hcloud_storage_box_subaccount.synology.home_directory
      }
    }
  }
}
