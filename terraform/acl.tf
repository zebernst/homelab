resource "tailscale_acl" "main" {
  # overwrite_existing_content bypasses the import requirement on first apply.
  # Remove this after initial setup if you prefer explicit import.
  overwrite_existing_content = true

  acl = jsonencode({
    tagOwners = {
      # Kubernetes operator — manages subnet routes and proxy devices
      "tag:k8s-operator" = ["autogroup:admin"]
      "tag:k8s"          = ["autogroup:admin"]
      # General servers (UDM Pro, NAS, etc.)
      "tag:server"       = ["autogroup:admin"]
    }

    acls = [
      # Default: allow all traffic. Tighten per-resource as needed.
      {
        action = "accept"
        src    = ["*"]
        dst    = ["*:*"]
      },
    ]

    ssh = [
      # Allow SSH from any tailnet device to tagged servers
      {
        action = "accept"
        src    = ["autogroup:member"]
        dst    = ["tag:server"]
        users  = ["autogroup:nonroot"]
      },
    ]
  })
}
