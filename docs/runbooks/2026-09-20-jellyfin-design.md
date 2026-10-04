# Jellyfin Deployment Design

**Date:** 2026-09-20  
**Status:** Approved  
**Approach:** GitOps shell + post-deploy SSO configuration

## Goal

Deploy Jellyfin on the homelab Kubernetes cluster so it:

1. Reads the same media libraries as Plex (NFS from Synology)
2. Authenticates users via Pocket ID (OIDC), with built-in login disabled after SSO works
3. Is reachable on LAN and Tailscale only (no public Cloudflare exposure)

## Non-goals

- Public (`external` Gateway / Cloudflare Tunnel) access
- Cilium LAN LoadBalancer for native clients
- GitOps automation of the Jellyfin SSO-Auth plugin XML/binary
- Jellyseerr / Seerr rewiring away from Plex
- Sharing Plex-specific paths (`posters`, optimized media)

## Architecture

```
Pocket ID (id.zebernst.dev)
        │ OIDC
        ▼
   Jellyfin SSO-Auth plugin
        │
   Jellyfin pod (media ns)
        ├── /config          Volsync PVC (ceph-block)
        ├── /cache,/tmp,/transcode  emptyDir
        └── /media/{tv,tv-uhd,movies,movies-uhd}  NFS RO ← nas.internal:/volume1/media
        │
        ├── HTTPRoute lan        → jellyfin.zebernst.dev
        └── HTTPRoute tailscale  → jellyfin.jptr.zebernst.dev
        │
        GPU: device plugin i915 (DRA deferred)
```

Flux applies `kubernetes/apps/media/jellyfin/` like other media apps. OIDC client credentials live in 1Password and sync via ExternalSecret; the SSO plugin itself is configured once in the Jellyfin UI after first boot.

## Placement & Flux

| Item | Value |
|------|--------|
| Path | `kubernetes/apps/media/jellyfin/` |
| Namespace | `media` |
| Registration | Add `jellyfin/ks.yaml` to `media/kustomization.yaml` |
| Components | `volsync`, `keda/nfs-scaler` |
| Depends on | `onepassword` (external-secrets), `rook-ceph-cluster`, `volsync`, HelmRelease `dependsOn` `intel-device-plugin-gpu` |
| Substitutes | `APP=jellyfin`, `VOLSYNC_CAPACITY=30Gi` |

Files:

```
jellyfin/
├── ks.yaml
└── app/
    ├── kustomization.yaml
    ├── ocirepository.yaml   # local Flux source named jellyfin → app-template
    ├── helmrelease.yaml
    └── externalsecret.yaml
```

## Runtime

- **Chart:** local `OCIRepository` `jellyfin` in the app dir (bjw-style), pointing at `oci://ghcr.io/bjw-s-labs/helm/app-template` with a pinned tag (e.g. `5.2.1`). HelmRelease `chartRef` references that local source — not the shared cluster `app-template` OCIRepository. There is no dedicated bjw-s jellyfin chart; this only isolates chart versioning per app.
- **Image:** `ghcr.io/jellyfin/jellyfin` (digest-pinned; Renovate can track)
- **Port:** `8096`
- **Env:**
  - `TZ: America/Chicago`
  - `DOTNET_SYSTEM_IO_DISABLEFILELOCKING: "true"`
  - `JELLYFIN_PublishedServerUrl: https://jellyfin.jptr.zebernst.dev` (canonical Tailscale URL; LAN hostname remains a first-class route)
- **Identity:** UID/GID `568`, `fsGroup: 568`, `supplementalGroups: [65568]` (render/GPU group, matching Plex/Stash)
- **GPU (v1):** classic device plugin — `gpu.intel.com/i915: 1`, `nodeSelector: intel.feature.node.kubernetes.io/gpu: "true"`, HelmRelease `dependsOn: intel-device-plugin-gpu`. DRA / `ResourceClaimTemplate` is deferred (requires `intel-gpu-resource-driver` and a Plex/Stash migration plan).
- **Priority:** `media-core` (internal media; not `external-facing`)
- **Probes:** HTTP GET `/health` on 8096 — gentler timings than Plex (e.g. period 30s, timeout 10s, failureThreshold 5 for liveness/readiness; startup period 10s, failureThreshold 30)
- **terminationGracePeriodSeconds:** `120` (avoid SIGKILL during Jellyfin 12 shutdown VACUUM; jellyfin#17831)
- **Resources:** requests `cpu: 100m`; limits `memory: 6Gi` (+ GPU limit as above)
- **Security:** non-root, drop ALL caps, no privilege escalation, `readOnlyRootFilesystem: true`
- **emptyDir tmpfs mounts:** `/cache`, `/tmp`, `/transcode` (required with RO rootfs)

## Storage

| Mount | Source | Mode | Purpose |
|-------|--------|------|---------|
| `/config` | Volsync PVC `jellyfin` | RW | App config, metadata DB, plugins |
| `/cache` | `emptyDir` (tmpfs) | RW | Cache scratch |
| `/tmp` | `emptyDir` (tmpfs) | RW | Temp (RO rootfs) |
| `/transcode` | `emptyDir` (tmpfs) | RW | Active transcodes |
| `/media/tv` | NFS `nas.internal:/volume1/media` subPath `tv` | RO | Same as Plex |
| `/media/tv-uhd` | subPath `tv-uhd` | RO | Same as Plex |
| `/media/movies` | subPath `movies` | RO | Same as Plex |
| `/media/movies-uhd` | subPath `movies-uhd` | RO | Same as Plex |

KEDA NFS scaler scales the Deployment to 0 when `nas.internal:2049` is unreachable (same component as Plex).

## Networking

- **Service:** ClusterIP on port 8096 (no LoadBalancer)
- **LAN route:** HTTPRoute parentRef `lan` / `https`, hostname `jellyfin.zebernst.dev`
- **Tailscale route:** HTTPRoute parentRef `tailscale` / `https-canon`, hostname `jellyfin.jptr.zebernst.dev`
- **Gatus:** per-route annotations with `name` + `group: media` (namespace), matching CLAUDE.md conventions
- **No** `external` parentRef

Both hostnames are first-class: Pocket ID callback URLs must include redirect URIs for each.

## Secrets & OIDC

### In Git / cluster

ExternalSecret `jellyfin` → Secret `jellyfin-secret` from 1Password item `jellyfin`:

- `POCKET_ID_CLIENT_ID`
- `POCKET_ID_CLIENT_SECRET`

These are staged for future automation and for operators to reference; the SSO-Auth plugin is configured via the Jellyfin dashboard on first bring-up (Approach 1). The HelmRelease does **not** env-inject or mount this Secret into the Jellyfin container in v1 — Jellyfin boots without it. ExternalSecret still runs so Reloader/ops have a synced `jellyfin-secret` once the 1Password item exists.

Optional Flux `dependsOn: pocket-id` is **not** required (Qui/Grafana do not declare it); Pocket ID must be available before SSO login works, but Jellyfin itself should start without the IdP.

### Post-deploy (operator, not GitOps)

1. Create Pocket ID OIDC client “Jellyfin” at `https://id.zebernst.dev` with:
   - Callback URLs:
     - `https://jellyfin.zebernst.dev/sso/OID/redirect/pocketid`
     - `https://jellyfin.jptr.zebernst.dev/sso/OID/redirect/pocketid`
   - PKCE enabled if available
   - Groups: create/use `jellyfin_users` and `jellyfin_admins` (or map existing groups explicitly in the plugin)
2. Store client id/secret in 1Password item `jellyfin` as `POCKET_ID_CLIENT_ID` / `POCKET_ID_CLIENT_SECRET`
3. Complete Jellyfin first-run wizard (temporary local admin)
4. Install **SSO-Auth** plugin (`9p4/jellyfin-plugin-sso`)
5. Configure provider name exactly `pocketid`:
   - OID Endpoint: `https://id.zebernst.dev` (or its OpenID discovery URL)
   - Client ID / Secret from Pocket ID
   - Role Claim: `groups`; additional scopes: `groups`
   - Roles: `jellyfin_users`; Admin Roles: `jellyfin_admins`
   - Scheme Override: `https`
   - Username claim: `preferred_username`
6. Verify login via `https://jellyfin.<host>/sso/OID/start/pocketid`
7. Disable Jellyfin built-in username/password login (SSO-only) once SSO admin access is confirmed
8. Add libraries pointing at `/media/tv`, `/media/tv-uhd`, `/media/movies`, `/media/movies-uhd`

Document these steps in the PR description (and optionally a short runbook under `docs/runbooks/` if one already exists for similar apps).

## Success criteria

- Flux reconciles `jellyfin` Kustomization healthy in `media`
- Pod scheduled on GPU node with i915 resource
- NFS libraries mounted RO; media browsable after library scan
- HTTPS works on `jellyfin.zebernst.dev` (LAN) and `jellyfin.jptr.zebernst.dev` (Tailscale)
- Pocket ID OIDC login works; local password login disabled
- Gatus discovers both routes under group `media`
- No secrets committed to Git

## Risks & notes

- **SSO plugin is not GitOps’d:** plugin upgrades or config loss on restore require re-applying SSO settings (Volsync backs `/config`, which should retain plugins if installed under config).
- **Dual callback URLs:** logging in from LAN vs Tailscale uses different hostnames; both must be registered in Pocket ID.
- **Native/TV apps:** browser SSO works; many Jellyfin clients need Quick Connect or similar for non-browser auth — out of scope for v1.
- **First-run local admin:** required briefly before SSO-only; do not leave a weak local admin once SSO is proven.
