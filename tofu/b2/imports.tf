# Import ID is the B2 bucket_id (not the name). See var.tofu_state_bucket_id.
import {
  to = b2_bucket.tofu_state
  id = "7fd2f810dd767980a00f0410"
}

import {
  to = b2_bucket.postgres_backup
  id = "ef52a8806d2669f0808f0410"
}

import {
  to = b2_bucket.volsync_backup
  id = "efe2c8f05d8669f0808f0410"
}

import {
  to = b2_bucket.nas_backup
  id = "af1278800da699f0805f0410"
}