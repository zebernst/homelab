# Jellyfin Implementation Plan

> **For agentic workers:** Implement task-by-task; checkboxes track progress.

**Goal:** Deploy Jellyfin in `media` with Plex NFS libraries, LAN+Tailscale routes, device-plugin GPU, and Pocket ID OIDC ExternalSecret staging.

**Architecture:** Flux Kustomization + Volsync + nfs-scaler; local `OCIRepository` named `jellyfin` → pinned `app-template` 5.2.1; HelmRelease mirrors Plex/Stash patterns; SSO plugin configured post-deploy.

**Tech Stack:** Flux, app-template, Jellyfin 12.1, External Secrets / 1Password, Intel device plugin.

## Global Constraints

- Namespace `media`; no `external` Gateway; no Cilium LB; no DRA
- UID/GID 568; NFS RO subPaths matching Plex libraries
- Do not commit secrets

---

### Task 1: Scaffold Flux app

- [ ] Create `kubernetes/apps/media/jellyfin/ks.yaml` (volsync, nfs-scaler, dependsOn, VOLSYNC_CAPACITY 30Gi)
- [ ] Create `app/kustomization.yaml`, `ocirepository.yaml`, `helmrelease.yaml`, `externalsecret.yaml`
- [ ] Register `jellyfin/ks.yaml` in `media/kustomization.yaml`
- [ ] Commit

### Task 2: Verify manifests

- [ ] YAML/schema sanity (anchors, paths, chartRef → local jellyfin OCIRepo)
- [ ] Commit any fixes; update PR with post-deploy OIDC runbook notes
