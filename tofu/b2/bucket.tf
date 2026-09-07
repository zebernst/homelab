# https://registry.terraform.io/providers/Backblaze/b2/latest/docs/resources/bucket
resource "b2_bucket" "tofu_state" {
  bucket_name = "jupiter-tofu-state"
  bucket_type = "allPrivate"

  default_server_side_encryption {
    algorithm = "AES256"
    mode      = "SSE-B2"
  }
}

resource "b2_bucket" "nas_backup" {
  bucket_name = "elohim-backup"
  bucket_type = "allPrivate"

  default_server_side_encryption {
    algorithm = "AES256"
    mode      = "SSE-B2"
  }

  # keep only latest version
  lifecycle_rules {
    file_name_prefix = ""
    days_from_hiding_to_deleting                           = 1
    days_from_starting_to_canceling_unfinished_large_files = 0
    days_from_uploading_to_hiding                          = 0
  }
}

resource "b2_bucket" "postgres_backup" {
  bucket_name = "cluster-db-backup"
  bucket_type = "allPrivate"

  default_server_side_encryption {
    algorithm = "AES256"
    mode      = "SSE-B2"
  }

  # keep only latest version
  lifecycle_rules {
    file_name_prefix = ""
    days_from_hiding_to_deleting                           = 1
    days_from_starting_to_canceling_unfinished_large_files = 0
    days_from_uploading_to_hiding                          = 0
  }
}

resource "b2_bucket" "volsync_backup" {
  bucket_name = "cluster-volsync-backup"
  bucket_type = "allPrivate"

  default_server_side_encryption {
    algorithm = "AES256"
    mode      = "SSE-B2"
  }

  # keep only latest version
  lifecycle_rules {
    file_name_prefix = ""
    days_from_hiding_to_deleting                           = 1
    days_from_starting_to_canceling_unfinished_large_files = 0
    days_from_uploading_to_hiding                          = 0
  }
}

