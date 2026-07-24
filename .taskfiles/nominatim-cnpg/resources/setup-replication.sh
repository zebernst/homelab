#!/bin/bash
# Runs *inside* the nominatim container. Piped in by
# `task nominatim-cnpg:setup-replication` (not mounted via ConfigMap).
#
# Idempotent: safe to re-run after rotating nominatim-replication password.
set -euo pipefail

REPL_USER="${REPL_USER:-cnpg_replica}"
REPL_PASSWORD="${REPL_PASSWORD:?REPL_PASSWORD is required}"
# Cluster pod CIDR (talos/machineconfig.yaml.j2 podSubnets); scoped to the
# replication pseudo-database and this role only.
REPL_CIDR="${REPL_CIDR:-10.244.0.0/16}"
HBA_LINE="host replication ${REPL_USER} ${REPL_CIDR} scram-sha-256"

# mediagis/nominatim uses Debian-style config under /etc/postgresql — not $PGDATA.
HBA_FILE="${HBA_FILE:-$(sudo -u postgres psql -At -c 'SHOW hba_file;' | tr -d '[:space:]')}"
if [ -z "${HBA_FILE}" ] || [ ! -f "${HBA_FILE}" ]; then
  echo "[setup-replication] ERROR: could not resolve hba_file (got '${HBA_FILE:-}')" >&2
  exit 1
fi
echo "[setup-replication] Using hba_file=${HBA_FILE}"

echo "[setup-replication] Ensuring role ${REPL_USER} exists with REPLICATION LOGIN"
# Use psql variables + \gexec so substitution works (variables do not expand
# inside dollar-quoted DO $$ blocks).
sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v repl_user="${REPL_USER}" \
  -v repl_password="${REPL_PASSWORD}" <<'SQL'
SELECT format(
  CASE
    WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'repl_user')
      THEN 'ALTER ROLE %I WITH REPLICATION LOGIN PASSWORD %L'
    ELSE 'CREATE ROLE %I WITH REPLICATION LOGIN PASSWORD %L'
  END,
  :'repl_user',
  :'repl_password'
)\gexec
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

echo "[setup-replication] Active replication HBA rules:"
sudo -u postgres psql -c \
  "SELECT type, database, user_name, address, auth_method
   FROM pg_hba_file_rules
   WHERE database @> ARRAY['replication']
   ORDER BY line_number;"

echo "[setup-replication] Current wal_level / max_wal_senders:"
sudo -u postgres psql -At -c "SHOW wal_level; SHOW max_wal_senders;"

echo "[setup-replication] Done."
