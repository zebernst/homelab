# Nominatim → CloudNativePG cutover

## Goal

Move Nominatim’s PostgreSQL database (~176 GB) out of the `mediagis/nominatim`
container into a dedicated CloudNativePG cluster (`nominatim-db`), then point
the Nominatim API at that cluster.

Until cutover finishes, Nominatim keeps serving from its **embedded** Postgres
on the `nominatim-pgdata` PVC. After cutover, Postgres runs only in CNPG;
Nominatim is an API (and OSM update) client.

## How the migration works

1. **Replicate.** CNPG takes a physical copy of the live DB (`pg_basebackup`)
  and streams WAL from the embedded Postgres until it is caught up.
2. **Promote.** Stop the API briefly, promote the CNPG copy to primary.
3. **Point the app.** Redeploy Nominatim with an external DB connection
  (`start-external.sh`) instead of starting local Postgres.
4. **Soak, then delete the old PVC.** Keep `nominatim-pgdata` until backups and
  a recovery check look good.

OSM update CronJobs stay **suspended** for the whole migration so incremental
updates do not race the replica.

## What to use when


| Kind                   | Where                   | Examples                                                                        |
| ---------------------- | ----------------------- | ------------------------------------------------------------------------------- |
| Durable cluster state  | Git → Flux              | `nominatim-db` Cluster, ObjectStore, secrets, app cutover manifests             |
| One-off operator steps | `task nominatim-cnpg:*` | Create replication role, preflight, lag check, scale API for the cutover window |


After cleanup, delete `.taskfiles/nominatim-cnpg/` and its include in the root
`Taskfile.yaml`.

## Prerequisites

- Prep PR merged (Barman plugin, `nominatim-db` app, source Service,
`start-external.sh` in the Nominatim ConfigMap but **not** yet the Deployment
command).
- 1Password item `nominatim-db`: `POSTGRES_SUPER_USER`, `POSTGRES_SUPER_PASS`,
`REPLICATION_PASS`.
- 1Password item `nominatim`: `NOMINATIM_PASSWORD` matches the `nominatim` DB
role (unchanged by the physical clone).
- OSM update CronJob still suspended.

```bash
task nominatim-cnpg:pg-source-status
task nominatim-cnpg:help
```

---



## 1. Allow CNPG to stream from embedded Postgres

Creates the `cnpg_replica` role and a `pg_hba` rule on the Nominatim pod’s
Postgres, then checks connectivity through Service `nominatim-pg-source`.

```bash
task nominatim-cnpg:setup-replication
task nominatim-cnpg:repl-preflight
```

Both are safe to re-run.

## 2. Wait for the replica to catch up

Flux should already be creating Cluster `nominatim-db` as a standalone replica
of the embedded DB.

```bash
task nominatim-cnpg:cnpg-status   # expect a healthy streaming replica
task nominatim-cnpg:repl-lag      # wait until lag is ~0
```

The base backup of ~176 GB can take a long time. Do not promote until lag is
essentially zero.

## 3. Promote CNPG (maintenance window)

Stop writes from the API, promote the replica, confirm PostGIS.

```bash
task nominatim-cnpg:cutover-scale-down   # suspend HelmRelease + scale API to 0
task nominatim-cnpg:repl-lag             # confirm still ~0
```

In git, set the cluster to primary and push:

```yaml
# kubernetes/apps/self-hosted/nominatim-db/app/cluster.yaml
replica:
  enabled: false
```

After Flux applies that:

```bash
kubectl -n self-hosted exec nominatim-db-1 -c postgres -- \
  psql -U postgres -d nominatim -c 'SELECT postgis_full_version();'
```

Leave the API at 0 replicas until the next step lands.

## 4. Point Nominatim at CNPG

Ship **one** git commit that does all of the following together (so Flux never
briefly feeds a CNPG DSN into the old local-Postgres startup path):

1. **ExternalSecret** (`kubernetes/apps/self-hosted/nominatim/app/externalsecret.yaml`)
  Keep `NOMINATIM_PASSWORD`. Add:

   ```yaml
   NOMINATIM_DATABASE_DSN: "pgsql:dbname=nominatim;host=nominatim-db-rw.self-hosted.svc;user=nominatim;password={{ .NOMINATIM_PASSWORD }}"
   PGHOST: nominatim-db-rw.self-hosted.svc
   PGDATABASE: nominatim
   PGUSER: nominatim
   PGPASSWORD: "{{ .NOMINATIM_PASSWORD }}"
   ```

2. **HelmRelease** (`kubernetes/apps/self-hosted/nominatim/app/helmrelease.yaml`)
  - Command: `/scripts/start-external.sh` (not `/scripts/start.sh`)
  - Remove embedded `POSTGRES_*` tuning env vars
  - Lower API memory (Postgres is no longer in this pod; e.g. ~4–8Gi)
  - Keep the OSM CronJob suspended
  - Keep the `pgdata` PVC defined but **unmounted** (`advancedMounts: {}`) so
  Helm does not delete the old data during soak

3. Drop `replica` / `externalClusters` from `nominatim-db`, rewrite bootstrap
  to `initdb` identity (`database`/`owner: nominatim`) so metrics still target
  the right DB, and remove Service `nominatim-pg-source`.

Push, then bring the API back:

```bash
task nominatim-cnpg:cutover-scale-up
```

Smoke-test:

```bash
kubectl -n self-hosted exec deploy/nominatim -c nominatim -- \
  curl -fsS http://127.0.0.1:8080/status

kubectl -n self-hosted exec deploy/nominatim -c nominatim -- \
  sudo -E -u nominatim nominatim admin --check-database --project-dir /nominatim
```

Also hit search, reverse, and the UI.

## 5. First backup and soak

Trigger a successful Barman/plugin backup (e.g. set ScheduledBackup
`immediate: true` once via git, confirm Completed, then turn it back off if you
want). Keep the OSM CronJob suspended until you are happy.

Soak through at least one successful scheduled backup.

## 6. Cleanup (separate PR, after soak)

Only after you trust CNPG + backups:

1. Remove `persistence.pgdata` from the HelmRelease.
2. Delete PVC `nominatim-pgdata` **only with an explicit go-ahead**.
3. Delete `.taskfiles/nominatim-cnpg/` and its include in the root `Taskfile.yaml`.
4. Re-enable the OSM update CronJob when ready for incremental updates again.

---



## Rollback

**Before promote** (`replica.enabled: true`): leave the app on `start.sh` and
the embedded PVC. You can abandon or recreate the CNPG cluster.

**After promote, during soak:** prefer restoring from a Barman backup onto a
new CNPG cluster. Remounting the old `nominatim-pgdata` is a last resort — it
will be stale relative to anything written on CNPG after promote.

## Related paths


| Path                                                                  | Role                                        |
| --------------------------------------------------------------------- | ------------------------------------------- |
| `kubernetes/apps/self-hosted/nominatim-db/`                           | CNPG Cluster, ObjectStore, backups, secrets |
| `kubernetes/apps/self-hosted/nominatim/app/scripts/start-external.sh` | External-DB entrypoint (used after step 4)  |
| `.taskfiles/nominatim-cnpg/`                                          | Temporary operator tasks for this migration |


