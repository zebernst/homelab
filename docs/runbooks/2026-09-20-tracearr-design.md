# Replace Tautulli with Tracearr

## Goal

Deploy Tracearr as the Plex (and multi-server) monitoring dashboard in the `media` namespace, using this repo’s Flux / app-template / CNPG patterns. Keep Tautulli running during an overlap window so history can be imported in the Tracearr UI. Remove Tautulli in a follow-up change after import.

## Decisions

| Topic | Choice |
| --- | --- |
| Packaging | app-template HelmRelease (not upstream Tracearr Helm chart) |
| Database | Dedicated CloudNativePG `Cluster` with TimescaleDB extension |
| Timescale image | Community CNPG-compatible image `ghcr.io/sedaprotocol/cnpg-timescaledb` (PG 18) |
| Redis | Sidecar in the Tracearr pod (not shared Dragonfly) |
| Cutover | Overlap: add Tracearr now; delete Tautulli later |
| Hostname | `tracearr.jptr.zebernst.dev` (Tailscale gateway) |
| CNPG storage | `ceph-block`, 50Gi |

## Architecture

```
                    tailscale Gateway (https-canon)
                              |
                    HTTPRoute tracearr.jptr.zebernst.dev
                              |
                    Service tracearr:3000
                              |
              ┌───────────────┴───────────────┐
              |  Pod (app-template)           |
              |  - tracearr (UID 1001)        |
              |  - redis:8 (localhost:6379)   |
              └───────────────┬───────────────┘
                              | DATABASE_URL
              ┌───────────────┴───────────────┐
              |  CNPG Cluster tracearr-db     |
              |  sedaprotocol/cnpg-timescaledb|
              |  barman → B2 ObjectStore      |
              └───────────────────────────────┘

Tautulli remains deployed until history import is done.
```

## Components

### Layout

```
kubernetes/apps/media/tracearr/
├── ks.yaml
└── app/
    ├── kustomization.yaml
    ├── helmrelease.yaml
    ├── externalsecret.yaml
    ├── cluster.yaml
    ├── objectstore.yaml
    ├── scheduledbackup.yaml
    └── vmprobe.yaml
```

Wire into `kubernetes/apps/media/kustomization.yaml` as `tracearr/ks.yaml`. Do not remove `tautulli/ks.yaml` in this change.

### Flux Kustomization

- `targetNamespace: media`
- Components: VolSync (app PVC)
- `dependsOn`: `cloudnative-pg` + `cloudnative-pg-barman-plugin` (database), `onepassword` (external-secrets), `rook-ceph-cluster`, `volsync`
- `postBuild.substitute`: `APP: tracearr`, `VOLSYNC_CAPACITY: 15Gi` (and PUID/PGID `1001` if VolSync requires them)

### HelmRelease (app-template)

- Controller: Tracearr container + Redis sidecar
- Image: `ghcr.io/connorgallopo/tracearr` (stable tag, Renovate-friendly digest pin)
- Env: `NODE_ENV=production`, `HOST=0.0.0.0`, `TZ=America/Chicago`, `REDIS_URL=redis://localhost:6379`, plus secret-ref for `DATABASE_URL`, `JWT_SECRET`, `COOKIE_SECRET`
- Probes: HTTP `/health` on port 3000 (liveness, readiness, startup)
- Security: run as 1001:1001, drop ALL caps; Redis sidecar similarly constrained
- Priority: `media-core`
- Route: Tailscale `https-canon`, hostname `tracearr.jptr.zebernst.dev`, Gatus endpoint annotation (`name` / `group: media`)
- Persistence (single VolSync claim `tracearr`, subPaths):
  - `/data/backup`
  - `/app/data/image-cache`

### CNPG Cluster `tracearr-db`

- `instances: 1`
- `imageName: ghcr.io/sedaprotocol/cnpg-timescaledb` pinned to a dated/immutable `18-ts2.26.x` tag at implement time
- Storage: `50Gi`, `storageClass: ceph-block`
- Bootstrap initdb database/owner: `tracearr` / app role (or dawarich-equivalent superuser-owned DB named `tracearr`)
- `postgresql.parameters`:
  - `shared_preload_libraries: timescaledb`
  - `timescaledb.license: timescale` (CNPG parameter form; required for compression/CAGGs)
  - Timescale-friendly locks/connections (`max_locks_per_transaction`, `max_connections` headroom for imports)
- Bootstrap `postInitApplicationSQL`:
  - `CREATE EXTENSION IF NOT EXISTS timescaledb;`
  - `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
- Superuser + app credentials via ExternalSecret (dawarich-shaped)
- Barman cloud plugin: ObjectStore under `s3://cluster-db-backup/tracearr-db/`, ScheduledBackup `@daily`
- Monitoring: enable PodMonitor if other dedicated clusters do

**Toolkit note:** Tracearr’s external-DB docs also mention `timescaledb_toolkit`. The sedaprotocol image ships TimescaleDB but not necessarily toolkit. Implementation must verify Tracearr migrations succeed; if toolkit is required, switch to a toolkit-capable CNPG image or add a follow-up image decision — do not silently ignore migration failures.

### Secrets (1Password item `tracearr`)

Create a 1Password item named `tracearr` with at least:

| Field | Purpose |
| --- | --- |
| `POSTGRES_SUPER_USER` | CNPG superuser username (e.g. `postgres`) |
| `POSTGRES_SUPER_PASS` | CNPG superuser password (URL-safe preferred — used in `DATABASE_URL`) |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `COOKIE_SECRET` | `openssl rand -hex 32` |

ExternalSecrets produce:

- `tracearr-db-secret` — CNPG superuser (`username` / `password`) with `cnpg.io/reload: "true"`
- `tracearr-db-backup-secret` — B2 keys from `barman-b2-credentials` (same pattern as dawarich)
- `tracearr-secret` — app env (`DATABASE_URL`, `JWT_SECRET`, `COOKIE_SECRET`)

Operator must create/populate the 1Password item before Flux can reconcile healthy.

### Observability

- HTTPRoute Gatus annotation (private instance discovers Tailscale routes)
- `VMProbe` blackbox against `http://tracearr.media.svc.cluster.local:3000/health`

## Cutover

1. Land Tracearr GitOps + 1Password item.
2. Wait for CNPG healthy, then Tracearr Ready.
3. Open Tracearr UI → complete setup → connect Plex.
4. Import Tautulli history while Tautulli is still available.
5. Follow-up PR: delete `kubernetes/apps/media/tautulli/` and remove it from `media/kustomization.yaml`.

No automated history import in GitOps.

## Sizing

| Resource | Requests | Limits | Notes |
| --- | --- | --- | --- |
| Tracearr | 100m CPU, 512Mi | 2Gi memory | Upstream ~1GB guidance |
| Redis sidecar | 5m CPU, 32Mi | 128Mi | No AOF; ephemeral jobs |
| CNPG | 250m CPU, 1Gi | 4Gi memory | 50Gi ceph-block |
| App VolSync PVC | — | 15Gi | backups + image cache |

## Out of scope

- Removing Tautulli (follow-up after import)
- Wiring Plex credentials in Git (UI configuration)
- Official Tracearr Helm chart
- Shared Dragonfly / shared `redspot` Postgres
- Building a custom CNPG Timescale image (unless toolkit forces it)

## Success criteria

- Tracearr reachable at `https://tracearr.jptr.zebernst.dev`
- CNPG cluster healthy with TimescaleDB extension enabled
- App connects to DB and Redis; `/health` passes
- Tautulli still deployed and usable for import
- Gatus / blackbox probe cover the new service
