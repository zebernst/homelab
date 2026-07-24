#!/bin/bash
# External-DB entrypoint: never starts local Postgres / never runs /app/init.sh.
# Wired as the Deployment command in the CNPG cutover (Task 6).
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/nominatim}"
STAGING_DIR="${IMPORT_STAGING:-/import-staging}"
# Gating marker lives on the project volume (not pgdata) after CNPG cutover.
IMPORT_FINISHED="${IMPORT_FINISHED:-${PROJECT_DIR}/import-finished}"
PGDATA="${PGDATA:-/var/lib/postgresql/16/main}"

: "${NOMINATIM_DATABASE_DSN:?NOMINATIM_DATABASE_DSN is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

# Prefer process env (ExternalSecret) over any durable .env DSN — never write
# the password-bearing DSN onto the project PVC.
export NOMINATIM_DATABASE_DSN PGHOST PGDATABASE PGUSER PGPASSWORD

mkdir -p "${STAGING_DIR}" "${PROJECT_DIR}"

link_staging() {
  local name="$1"
  local link="${PROJECT_DIR}/${name}"
  local target="${STAGING_DIR}/${name}"

  if [ -e "${link}" ] && [ ! -L "${link}" ]; then
    echo "Removing stale import artifact from project volume: ${link}"
    rm -f "${link}"
  fi

  ln -sfn "${target}" "${link}"
}

link_staging "data.osm.pbf"
link_staging "wikimedia-importance.csv.gz"
link_staging "us_postcodes.csv.gz"
link_staging "secondary_importance.sql.gz"

# One-time migration: copy legacy pgdata marker onto the project volume when
# the old PVC is still mounted.
if [ ! -f "${IMPORT_FINISHED}" ] && [ -f "${PGDATA}/import-finished" ]; then
  echo "[nominatim] Migrating import-finished marker from ${PGDATA} to ${IMPORT_FINISHED}"
  cp -a "${PGDATA}/import-finished" "${IMPORT_FINISHED}"
fi

# Project PVC mounts over /nominatim and hides the image's baked-in .env.
# Seed non-secret defaults only; strip any password-bearing DSN if present.
if [ ! -f "${PROJECT_DIR}/.env" ]; then
  echo "[nominatim] Seeding ${PROJECT_DIR}/.env from /scripts/env.defaults"
  cp /scripts/env.defaults "${PROJECT_DIR}/.env"
fi

ENV_FILE="${PROJECT_DIR}/.env"
IMPORT_STYLE="${IMPORT_STYLE:-extratags}"
if [ -f "${ENV_FILE}" ] && grep -qE '^NOMINATIM_IMPORT_STYLE=' "${ENV_FILE}"; then
  sed -i "s|^NOMINATIM_IMPORT_STYLE=.*|NOMINATIM_IMPORT_STYLE=${IMPORT_STYLE}|" "${ENV_FILE}"
elif [ -f "${ENV_FILE}" ] && grep -q '__IMPORT_STYLE__' "${ENV_FILE}"; then
  sed -i "s|__IMPORT_STYLE__|${IMPORT_STYLE}|g" "${ENV_FILE}"
fi

if [ -n "${NOMINATIM_FLATNODE_FILE:-}" ]; then
  if grep -qE '^NOMINATIM_FLATNODE_FILE=' "${ENV_FILE}"; then
    sed -i "s|^NOMINATIM_FLATNODE_FILE=.*|NOMINATIM_FLATNODE_FILE=${NOMINATIM_FLATNODE_FILE}|" "${ENV_FILE}"
  else
    printf 'NOMINATIM_FLATNODE_FILE=%s\n' "${NOMINATIM_FLATNODE_FILE}" >> "${ENV_FILE}"
  fi
fi

echo "[nominatim] Waiting for PostgreSQL at ${PGHOST}"
until pg_isready -h "${PGHOST}" -d "${PGDATABASE}" -U "${PGUSER}" -q; do
  sleep 2
done

# Fail closed: only seed the project marker when CNPG actually has Nominatim data.
if [ ! -f "${IMPORT_FINISHED}" ]; then
  echo "[nominatim] Verifying nominatim schema on ${PGHOST}/${PGDATABASE} before seeding import-finished"
  has_placex="$(psql -h "${PGHOST}" -d "${PGDATABASE}" -U "${PGUSER}" -Atqc \
    "SELECT EXISTS (
       SELECT 1
       FROM pg_catalog.pg_class c
       JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
       WHERE n.nspname = 'public' AND c.relname = 'placex' AND c.relkind = 'r'
     );")"
  if [ "${has_placex}" != "t" ]; then
    echo "[nominatim] ERROR: public.placex missing on ${PGHOST}; refusing to seed import-finished" >&2
    exit 1
  fi
  echo "[nominatim] Seeding ${IMPORT_FINISHED}"
  touch "${IMPORT_FINISHED}"
fi

echo "[nominatim] Refreshing website + SQL functions against external DB"
sudo -E -u nominatim nominatim refresh --website --functions --project-dir "${PROJECT_DIR}"

if [ -z "${GUNICORN_WORKERS:-}" ]; then
  GUNICORN_WORKERS="$(nproc)"
fi

echo "[nominatim] Starting Gunicorn on :8080 with ${GUNICORN_WORKERS} workers (foreground)"
cd "${PROJECT_DIR}"
# Foreground (no --daemon): container PID must be the API process under Kubernetes.
exec sudo -E -u nominatim gunicorn \
  --bind :8080 \
  --workers "${GUNICORN_WORKERS}" \
  --enable-stdio-inheritance \
  --worker-class uvicorn.workers.UvicornWorker \
  nominatim_api.server.falcon.server:run_wsgi
