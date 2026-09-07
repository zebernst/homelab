output "tofu_state_bucket" {
  description = "OpenTofu remote-state bucket"
  value = {
    id   = b2_bucket.tofu_state.bucket_id
    name = b2_bucket.tofu_state.bucket_name
    type = b2_bucket.tofu_state.bucket_type
  }
}

output "nas_backup_bucket" {
  description = "NAS backup bucket"
  value = {
    id   = b2_bucket.nas_backup.bucket_id
    name = b2_bucket.nas_backup.bucket_name
    type = b2_bucket.nas_backup.bucket_type
  }
}

output "postgres_backup_bucket" {
  description = "Postgres/CNPG backup bucket"
  value = {
    id   = b2_bucket.postgres_backup.bucket_id
    name = b2_bucket.postgres_backup.bucket_name
    type = b2_bucket.postgres_backup.bucket_type
  }
}

output "volsync_backup_bucket" {
  description = "Volsync backup bucket"
  value = {
    id   = b2_bucket.volsync_backup.bucket_id
    name = b2_bucket.volsync_backup.bucket_name
    type = b2_bucket.volsync_backup.bucket_type
  }
}
