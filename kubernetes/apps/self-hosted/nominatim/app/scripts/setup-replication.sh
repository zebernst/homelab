#!/bin/bash
# Runs *inside* the nominatim container (invoked via `kubectl exec` from the
# nominatim-setup-replication Job; see ../job-setup-replication.yaml).
#
# GitOps-safe replacement for imperative `kubectl exec ... CREATE ROLE` /
# pg_hba edits: this script is idempotent so the (normally suspended) Job can
# be re-run safely after a password rotation without side effects.
set -euo pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/16/main}"
HBA_FILE="${PGDATA}/pg_hba.conf"
REPL_USER="${REPL_USER:-cnpg_replica}"
REPL_PASSWORD="${REPL_PASSWORD:?REPL_PASSWORD is required}"
# Cluster pod CIDR (talos/machineconfig.yaml.j2 podSubnets); scoped to the
# replication pseudo-database and this role only.
REPL_CIDR="${REPL_CIDR:-10.244.0.0/16}"
HBA_LINE="host replication ${REPL_USER} ${REPL_CIDR} scram-sha-256"

echo "[setup-replication] Ensuring role ${REPL_USER} exists with REPLICATION LOGIN"
sudo -u postgres psql -v ON_ERROR_STOP=1 -v repl_user="${REPL_USER}" -v repl_password="${REPL_PASSWORD}" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'repl_user') THEN
    EXECUTE format('CREATE ROLE %I WITH REPLICATION LOGIN PASSWORD %L', :'repl_user', :'repl_password');
  ELSE
    EXECUTE format('ALTER ROLE %I WITH REPLICATION LOGIN PASSWORD %L', :'repl_user', :'repl_password');
  END IF;
END
$$;
SQL

echo "[setup-replication] Ensuring pg_hba.conf allows replication from ${REPL_CIDR}"
if sudo -u postgres grep -qxF "${HBA_LINE}" "${HBA_FILE}"; then
  echo "[setup-replication] pg_hba.conf already contains the replication entry; skipping append"
else
  sudo -u postgres bash -c "printf '%s\n' \"${HBA_LINE}\" >> \"${HBA_FILE}\""
  echo "[setup-replication] Appended: ${HBA_LINE}"
fi

echo "[setup-replication] Reloading PostgreSQL configuration"
sudo -u postgres psql -v ON_ERROR_STOP=1 -c 'SELECT pg_reload_conf();'

echo "[setup-replication] Current wal_level / max_wal_senders:"
sudo -u postgres psql -At -c "SHOW wal_level; SHOW max_wal_senders;"

echo "[setup-replication] Done."
