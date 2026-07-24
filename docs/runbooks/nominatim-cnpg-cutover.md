# Nominatim → CloudNativePG cutover runbook

GitOps-only: every cluster change is a git commit for Flux. Do not `kubectl apply`,
`kubectl patch`, or imperative `flux reconcile` as deploy. Read-only `kubectl get` /
`logs` / `exec` for verification is fine.

## Split

| Phase | What lands in git | When |
|-------|-------------------|------|
| Prep | Barman plugin, `nominatim-db` Cluster (replica), source Service, suspended setup Job, `start-external.sh` in ConfigMap (unused), this runbook | Merge anytime |
| Cutover | Promote `replica.enabled: false`; flip HelmRelease + ExternalSecret DSN (Phase D below) | Ops window after streaming lag ≈ 0 |
| Cleanup | Remove source Service/Job; delete unmounted `nominatim-pgdata` | After soak + recovery test |

## Preconditions

- [ ] 1Password item `nominatim-db` has `POSTGRES_SUPER_USER`, `POSTGRES_SUPER_PASS`, `REPLICATION_PASS`
- [ ] 1Password `nominatim` / `NOMINATIM_PASSWORD` matches the cloned `nominatim` DB role
- [ ] OSM update CronJob remains `suspend: true` (`task nominatim:pg-source-status`)

## Phase A — Source replication prep

1. `task nominatim:pg-source-status` — CronJob suspended; Service present after Flux.
2. Enable setup Job: set `spec.suspend: false` in
   `kubernetes/apps/self-hosted/nominatim/app/job-setup-replication.yaml`, commit, push.
3. Wait for Job success; re-suspend (`suspend: true`), commit.
4. Optional: `pg_isready` / `IDENTIFY_SYSTEM` against `nominatim-pg-source.self-hosted.svc`.

## Phase B — Replica bootstrap

1. Confirm Cluster `nominatim-db` completed `pg_basebackup` and is streaming.
2. Wait until replication lag ≈ 0.
3. Soft affinity should prefer the nominatim API/flatnode node.

## Phase C — Promote

1. Scale nominatim Deployment to 0 via git (temporary `replicas: 0` on the controller), commit.
2. Wait for lag 0 again.
3. In `kubernetes/apps/self-hosted/nominatim-db/app/cluster.yaml` set:
   ```yaml
   replica:
     enabled: false
   ```
   (remove or leave `source` per CNPG docs after promote.) Commit, push.
4. Verify PostGIS on primary:
   ```bash
   kubectl -n self-hosted exec nominatim-db-1 -c postgres -- \
     psql -U postgres -d nominatim -c 'SELECT postgis_full_version();'
   ```

## Phase D — App cutover (follow-up commit during ops window)

Apply all of the following in **one** commit so Flux does not briefly inject DSN into
`start.sh`:

### 1. ExternalSecret (`app/externalsecret.yaml`)

Add to `target.template.data` (keep `NOMINATIM_PASSWORD`):

```yaml
NOMINATIM_DATABASE_DSN: "pgsql:dbname=nominatim;host=nominatim-db-rw.self-hosted.svc;user=nominatim;password={{ .NOMINATIM_PASSWORD }}"
PGHOST: nominatim-db-rw.self-hosted.svc
PGDATABASE: nominatim
PGUSER: nominatim
PGPASSWORD: "{{ .NOMINATIM_PASSWORD }}"
```

### 2. HelmRelease (`app/helmrelease.yaml`)

- `command: ["/bin/bash", "/scripts/start-external.sh"]`
- Remove `POSTGRES_SHARED_BUFFERS` / `POSTGRES_MAINTENANCE_WORK_MEM` /
  `POSTGRES_AUTOVACUUM_WORK_MEM` / `POSTGRES_EFFECTIVE_CACHE_SIZE`
- Resources: e.g. requests `memory: 4Gi`, limits `memory: 8Gi` (API-only)
- Startup `failureThreshold: 40` (no multi-day import on boot)
- Keep CronJob `suspend: true`
- **Retain** `persistence.pgdata` PVC but set `advancedMounts: {}` so Helm does not
  delete the claim through soak

### 3. Restore replicas

Set Deployment replicas back to 1 in the same commit if scaled down in Phase C.

### 4. Verify

```bash
kubectl -n self-hosted exec deploy/nominatim -c nominatim -- curl -fsS http://127.0.0.1:8080/status
kubectl -n self-hosted exec deploy/nominatim -c nominatim -- \
  sudo -E -u nominatim nominatim admin --check-database --project-dir /nominatim
# search, reverse, UI
```

### 5. Backup

Set `ScheduledBackup` `immediate: true` once (or add a one-shot Backup) via git;
confirm plugin backup Completes. Then set `immediate: false` again if desired.

## Phase E — Soak and cleanup

1. Soak until ≥ one successful daily/plugin backup; CronJob still suspended.
2. Cleanup PR: remove `nominatim-pg-source`, setup Job/RBAC, replication script;
   remove `persistence.pgdata` from HelmRelease; delete PVC `nominatim-pgdata` only
   after explicit confirmation.

## Rollback

- **Before promote:** keep `replica.enabled: true`; app stays on `start.sh` + pgdata.
- **After promote / before soak ends:** prefer Barman restore to a new Cluster; remounting
  stale `nominatim-pgdata` is last resort.
