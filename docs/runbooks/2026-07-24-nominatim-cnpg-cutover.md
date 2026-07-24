# Nominatim → CloudNativePG cutover runbook

Durable state is IaC (git → Flux): the `nominatim-db` Cluster/ObjectStore/secrets,
the source Service, and the Phase D app cutover commit. One-off migration steps
(role setup, preflight, scaling for the cutover window) are local Taskfile
executions from the operator's machine — they are short-lived and not worth
encoding as committed Jobs.

## Split

| Phase | Mechanism | When |
|-------|-----------|------|
| Prep manifests | Git → Flux: Barman plugin, `nominatim-db` Cluster (replica), source Service, `start-external.sh` in ConfigMap (unused) | Merge anytime |
| One-off setup | Taskfile: `setup-replication`, `repl-preflight` | After prep merge |
| Cutover | Taskfile scale-down + git: promote `replica.enabled: false`, flip HelmRelease + ExternalSecret DSN (Phase D) | Ops window after lag ≈ 0 |
| Cleanup | Git: remove source Service + replication script; delete unmounted `nominatim-pgdata` | After soak + recovery test |

## Preconditions

- [ ] 1Password item `nominatim-db` has `POSTGRES_SUPER_USER`, `POSTGRES_SUPER_PASS`, `REPLICATION_PASS`
- [ ] 1Password `nominatim` / `NOMINATIM_PASSWORD` matches the cloned `nominatim` DB role
- [ ] OSM update CronJob remains `suspend: true` (`task nominatim-cnpg:pg-source-status`)

## Phase A — Source replication prep (Taskfile, one-off)

1. `task nominatim-cnpg:pg-source-status` — CronJob suspended; Service present after Flux.
2. `task nominatim-cnpg:setup-replication` — creates/updates the `cnpg_replica` role,
   appends the pg_hba entry, reloads config (idempotent; script lives under
   `.taskfiles/nominatim-cnpg/resources/` and is piped into the pod via stdin).
3. `task nominatim-cnpg:repl-preflight` — throwaway pod runs `pg_isready` +
   `IDENTIFY_SYSTEM` against `nominatim-pg-source.self-hosted.svc`.

## Phase B — Replica bootstrap

1. Confirm Cluster `nominatim-db` completed `pg_basebackup` and is streaming
   (`task nominatim-cnpg:cnpg-status`).
2. Wait until replication lag ≈ 0 (`task nominatim-cnpg:repl-lag`).
3. Soft affinity should prefer the nominatim API/flatnode node.

## Phase C — Promote

1. `task nominatim-cnpg:cutover-scale-down` — suspends the Flux HelmRelease and scales
   the nominatim API to 0 for the window.
2. Wait for lag 0 again (`task nominatim-cnpg:repl-lag`).
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

Push the commit, then `task nominatim-cnpg:cutover-scale-up` (scales the API back to 1
and resumes the Flux HelmRelease so the cutover values roll out).

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
2. Cleanup PR: remove `nominatim-pg-source` Service; remove `persistence.pgdata`
   from the HelmRelease; delete PVC `nominatim-pgdata` only after explicit confirmation.
   Delete `.taskfiles/nominatim-cnpg/` and remove its include from the root
   `Taskfile.yaml`.

## Rollback

- **Before promote:** keep `replica.enabled: true`; app stays on `start.sh` + pgdata.
- **After promote / before soak ends:** prefer Barman restore to a new Cluster; remounting
  stale `nominatim-pgdata` is last resort.
