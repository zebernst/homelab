variable "storage_box_password" {
  description = "Primary Storage Box password (Hetzner policy: ≥12 chars, ≥1 special). Also written to the 1Password item."
  type        = string
  sensitive   = true
}
