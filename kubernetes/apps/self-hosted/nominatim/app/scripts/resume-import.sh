#!/bin/bash
# Resume an interrupted mediagis/nominatim bootstrap import.
#
# Exit codes:
#   0 — import finished (import-finished written); safe to run /app/start.sh
#   1 — fatal; do NOT fall through to /app/init.sh (it DROP DATABASE)
#   2 — no resumable Nominatim data; safe to let /app/init.sh run a fresh import
#
# Override stage with NOMINATIM_CONTINUE_AT=import-from-file|load-data|indexing|db-postprocess
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/nominatim}"
STAGING_DIR="${IMPORT_STAGING:-/import-staging}"
PGDATA="${PGDATA:-/var/lib/postgresql/16/main}"
IMPORT_FINISHED="${IMPORT_FINISHED:-${PGDATA}/import-finished}"
OSMFILE="${PBF_PATH:-${STAGING_DIR}/data.osm.pbf}"
THREADS="${THREADS:-$(nproc)}"
IMPORT_CONF_SRC="/etc/postgresql/16/main/conf.d/postgres-import.conf.disabled"
IMPORT_CONF_DST="/etc/postgresql/16/main/conf.d/postgres-import.conf"

log() { echo "[nominatim-resume] $*"; }

psql_scalar() {
  sudo -E -u postgres psql -d nominatim -Atqc "$1" 2>/dev/null || true
}

db_exists() {
  sudo -E -u postgres psql -d postgres -Atqc \
    "SELECT 1 FROM pg_database WHERE datname = 'nominatim'" 2>/dev/null | grep -q 1
}

enable_import_conf() {
  if [ -f "${IMPORT_CONF_SRC}" ]; then
    cp "${IMPORT_CONF_SRC}" "${IMPORT_CONF_DST}"
  fi
}

disable_import_conf() {
  rm -f "${IMPORT_CONF_DST}"
}

ensure_roles() {
  sudo -E -u postgres psql -d postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname='nominatim'" | grep -q 1 \
    || sudo -E -u postgres createuser -s nominatim
  sudo -E -u postgres psql -d postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname='www-data'" | grep -q 1 \
    || sudo -E -u postgres createuser -SDR www-data
  if [ -n "${NOMINATIM_PASSWORD:-}" ]; then
    sudo -E -u postgres psql -d postgres -c \
      "ALTER USER nominatim WITH ENCRYPTED PASSWORD '${NOMINATIM_PASSWORD}'"
    sudo -E -u postgres psql -d postgres -c \
      "ALTER USER \"www-data\" WITH ENCRYPTED PASSWORD '${NOMINATIM_PASSWORD}'"
  fi
}

start_postgres() {
  enable_import_conf
  if pg_isready -q 2>/dev/null; then
    log "Postgres already running"
    return 0
  fi
  log "Starting Postgres"
  service postgresql start
  for _ in $(seq 1 60); do
    pg_isready -q && return 0
    sleep 1
  done
  log "Postgres failed to become ready"
  return 1
}

stop_postgres() {
  if pg_isready -q 2>/dev/null; then
    log "Stopping Postgres"
    service postgresql stop || true
  fi
  disable_import_conf
}

ensure_osm_file() {
  if [ -n "${PBF_PATH:-}" ] && [ -f "${PBF_PATH}" ] && [ -s "${PBF_PATH}" ]; then
    OSMFILE="${PBF_PATH}"
    log "Using PBF_PATH=${OSMFILE}"
    return 0
  fi

  mkdir -p "${STAGING_DIR}"
  if [ -f "${OSMFILE}" ] && [ -s "${OSMFILE}" ]; then
    log "Using existing OSM extract (${OSMFILE})"
    return 0
  fi

  if [ -z "${PBF_URL:-}" ]; then
    log "OSM extract missing at ${OSMFILE} and PBF_URL is unset"
    return 1
  fi

  log "Re-downloading OSM extract from ${PBF_URL}"
  curl -L -A "${USER_AGENT:-nominatim}" --fail-with-body -C - --create-dirs \
    -o "${OSMFILE}" "${PBF_URL}"
}

# Detect --continue checkpoint from DB state (see nominatim_db/tools/database_import.py
# and clicmd/setup.py). Prints one of: done|import-from-file|load-data|indexing|db-postprocess|fresh
detect_continue_at() {
  if [ -n "${NOMINATIM_CONTINUE_AT:-}" ]; then
    echo "${NOMINATIM_CONTINUE_AT}"
    return 0
  fi

  if ! db_exists; then
    echo "fresh"
    return 0
  fi

  local has_place has_placex_rel placex_loaded indexing_started has_pending has_version

  has_place="$(psql_scalar "SELECT COALESCE((SELECT true FROM place LIMIT 1), false)")"
  if [ "${has_place}" != "t" ] && [ "${has_place}" != "true" ]; then
    # No successful osm2pgsql output — safer to let init.sh DROP + re-import.
    echo "fresh"
    return 0
  fi

  has_placex_rel="$(psql_scalar "SELECT to_regclass('public.placex') IS NOT NULL")"
  if [ "${has_placex_rel}" != "t" ] && [ "${has_placex_rel}" != "true" ]; then
    echo "import-from-file"
    return 0
  fi

  placex_loaded="$(psql_scalar "SELECT EXISTS (SELECT 1 FROM placex LIMIT 1)")"
  if [ "${placex_loaded}" != "t" ] && [ "${placex_loaded}" != "true" ]; then
    echo "load-data"
    return 0
  fi

  has_version="$(psql_scalar \
    "SELECT EXISTS (SELECT 1 FROM nominatim_properties WHERE property = 'database_version')")"
  if [ "${has_version}" = "t" ] || [ "${has_version}" = "true" ]; then
    echo "done"
    return 0
  fi

  # indexed_status: 0 = indexed; >0 = pending (load_data insert triggers set 1)
  indexing_started="$(psql_scalar \
    "SELECT EXISTS (SELECT 1 FROM placex WHERE indexed_status = 0 LIMIT 1)")"
  if [ "${indexing_started}" != "t" ] && [ "${indexing_started}" != "true" ]; then
    # Placex loaded but indexing never committed a row — still in postcodes or pre-index.
    # --continue indexing would skip postcodes; use load-data.
    echo "load-data"
    return 0
  fi

  has_pending="$(psql_scalar \
    "SELECT EXISTS (SELECT 1 FROM placex WHERE indexed_status > 0 LIMIT 1)")"
  if [ "${has_pending}" = "t" ] || [ "${has_pending}" = "true" ]; then
    echo "indexing"
    return 0
  fi

  echo "db-postprocess"
}

run_continue() {
  local stage="$1"
  chown -R nominatim:nominatim "${PROJECT_DIR}"

  case "${stage}" in
    import-from-file)
      ensure_osm_file
      log "Running: nominatim import --continue import-from-file --osm-file ${OSMFILE}"
      cd "${PROJECT_DIR}"
      sudo -E -u nominatim nominatim import \
        --continue import-from-file \
        --osm-file "${OSMFILE}" \
        --threads "${THREADS}"
      ;;
    load-data | indexing | db-postprocess)
      log "Running: nominatim import --continue ${stage}"
      cd "${PROJECT_DIR}"
      sudo -E -u nominatim nominatim import \
        --continue "${stage}" \
        --threads "${THREADS}"
      ;;
    *)
      log "Unknown continue stage: ${stage}"
      return 1
      ;;
  esac

  # Match init.sh post-import checks (best-effort; import itself is the critical path).
  sudo -E -u nominatim nominatim index --threads "${THREADS}" || true
  sudo -E -u nominatim nominatim admin --check-database
}

mark_finished() {
  touch "${IMPORT_FINISHED}"
  log "Wrote ${IMPORT_FINISHED}"
}

cleanup() {
  stop_postgres
}
trap cleanup EXIT

if [ -f "${IMPORT_FINISHED}" ]; then
  log "import-finished already present; nothing to resume"
  trap - EXIT
  exit 0
fi

if [ ! -f "${PGDATA}/PG_VERSION" ]; then
  log "No Postgres datadir yet; deferring to init.sh"
  trap - EXIT
  exit 2
fi

start_postgres
ensure_roles

stage="$(detect_continue_at)"
log "Detected stage: ${stage}"

case "${stage}" in
  done)
    mark_finished
    trap - EXIT
    stop_postgres
    exit 0
    ;;
  fresh)
    log "No resumable import progress; deferring to init.sh"
    trap - EXIT
    stop_postgres
    exit 2
    ;;
  import-from-file | load-data | indexing | db-postprocess)
    run_continue "${stage}"
    mark_finished
    trap - EXIT
    stop_postgres
    exit 0
    ;;
  *)
    log "Unhandled stage '${stage}'"
    exit 1
    ;;
esac
