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
PBF_SIZE_MARKER="${PBF_SIZE_MARKER:-${PROJECT_DIR}/.bootstrap-pbf-bytes}"
THREADS="${THREADS:-$(nproc)}"
FLATNODE_FILE="${NOMINATIM_FLATNODE_FILE:-/nominatim/flatnode/flatnode.file}"
RESUME_LOCK="${RESUME_LOCK:-${PROJECT_DIR}/.resume-import.lock}"
IMPORT_CONF_SRC="/etc/postgresql/16/main/conf.d/postgres-import.conf.disabled"
IMPORT_CONF_DST="/etc/postgresql/16/main/conf.d/postgres-import.conf"

# Lifecycle flags: only reverse what this process changed (safe under kubectl exec).
STARTED_PG=0
ENABLED_IMPORT_CONF=0

# stderr so DETECT_ONLY / detect_continue_at can keep stage tokens on stdout only
log() { echo "[nominatim-resume] $*" >&2; }

psql_true() {
  case "$1" in
    t | true) return 0 ;;
    *) return 1 ;;
  esac
}

psql_scalar() {
  # Fail closed: never map probe errors to empty/"fresh" (that defers to init.sh DROP DATABASE).
  sudo -E -u postgres psql -d nominatim -Atqc "$1"
}

# Prints "exists" or "missing". Returns 1 on query failure (caller must not treat as missing).
probe_nominatim_db() {
  local out
  out="$(sudo -E -u postgres psql -d postgres -Atqc \
    "SELECT 1 FROM pg_database WHERE datname = 'nominatim'")" || return 1
  if [ "${out}" = "1" ]; then
    echo "exists"
  else
    echo "missing"
  fi
}

enable_import_conf() {
  if [ -f "${IMPORT_CONF_SRC}" ]; then
    cp "${IMPORT_CONF_SRC}" "${IMPORT_CONF_DST}"
    ENABLED_IMPORT_CONF=1
  fi
}

disable_import_conf() {
  if [ "${ENABLED_IMPORT_CONF}" = "1" ]; then
    rm -f "${IMPORT_CONF_DST}"
    ENABLED_IMPORT_CONF=0
  fi
}

set_role_password() {
  local role="$1"
  # Match mediagis init.sh. psql -v / :'pw' is not interpolated reliably with -c here.
  if [ -z "${NOMINATIM_PASSWORD:-}" ]; then
    return 0
  fi
  sudo -E -u postgres psql -d postgres -c \
    "ALTER USER \"${role}\" WITH ENCRYPTED PASSWORD '${NOMINATIM_PASSWORD}'"
}

ensure_roles() {
  # On resume the roles already exist from the interrupted import; only create/set
  # passwords when missing so we do not depend on ALTER for the common path.
  if ! sudo -E -u postgres psql -d postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname='nominatim'" | grep -q 1; then
    sudo -E -u postgres createuser -s nominatim
    set_role_password nominatim
  fi
  if ! sudo -E -u postgres psql -d postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname='www-data'" | grep -q 1; then
    sudo -E -u postgres createuser -SDR www-data
    set_role_password www-data
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
  STARTED_PG=1
  for _ in $(seq 1 60); do
    pg_isready -q && return 0
    sleep 1
  done
  log "Postgres failed to become ready"
  return 1
}

stop_postgres() {
  if [ "${STARTED_PG}" = "1" ] && pg_isready -q 2>/dev/null; then
    log "Stopping Postgres"
    service postgresql stop || true
  fi
  disable_import_conf
}

record_pbf_size() {
  local file="$1"
  if [ -f "${file}" ] && [ -s "${file}" ]; then
    mkdir -p "$(dirname "${PBF_SIZE_MARKER}")"
    stat -c %s "${file}" > "${PBF_SIZE_MARKER}"
    log "Recorded PBF size marker (${PBF_SIZE_MARKER})=$(cat "${PBF_SIZE_MARKER}")"
  fi
}

remote_pbf_size() {
  curl -fsIL --connect-timeout 30 --max-time 120 "${PBF_URL}" \
    | grep -Fi 'content-length:' | tail -n1 \
    | sed 's/.*:[[:space:]]*//' | tr -d '\r'
}

ensure_osm_file() {
  if [ -n "${PBF_PATH:-}" ] && [ -f "${PBF_PATH}" ] && [ -s "${PBF_PATH}" ]; then
    OSMFILE="${PBF_PATH}"
    log "Using PBF_PATH=${OSMFILE}"
    record_pbf_size "${OSMFILE}"
    return 0
  fi

  mkdir -p "${STAGING_DIR}"
  if [ -f "${OSMFILE}" ] && [ -s "${OSMFILE}" ]; then
    log "Using existing OSM extract (${OSMFILE})"
    record_pbf_size "${OSMFILE}"
    return 0
  fi

  if [ -z "${PBF_URL:-}" ]; then
    log "OSM extract missing at ${OSMFILE} and PBF_URL is unset"
    return 1
  fi

  # emptyDir often loses the extract across restarts; -latest may differ from the
  # PBF that produced existing place/flatnode. Refuse skew unless explicitly allowed.
  if [ -f "${PBF_SIZE_MARKER}" ]; then
    local expected remote
    expected="$(tr -d '[:space:]' < "${PBF_SIZE_MARKER}")"
    remote="$(remote_pbf_size || true)"
    if [ -n "${expected}" ] && [ -n "${remote}" ] && [ "${expected}" != "${remote}" ] \
      && [ "${NOMINATIM_ALLOW_PBF_REDOWNLOAD:-}" != "1" ]; then
      log "Refusing PBF re-download: marker ${expected} bytes != remote ${remote} bytes"
      log "Set NOMINATIM_ALLOW_PBF_REDOWNLOAD=1 to override, or restore the original extract to ${OSMFILE}"
      return 1
    fi
  elif [ "${NOMINATIM_ALLOW_PBF_REDOWNLOAD:-}" != "1" ]; then
    log "OSM extract missing and no ${PBF_SIZE_MARKER}; refusing blind -latest re-download"
    log "Restore data.osm.pbf to ${OSMFILE}, or set NOMINATIM_ALLOW_PBF_REDOWNLOAD=1"
    return 1
  fi

  log "Re-downloading OSM extract from ${PBF_URL}"
  curl -L -A "${USER_AGENT:-nominatim}" --fail-with-body -C - --create-dirs \
    --connect-timeout 30 --max-time 21600 \
    -o "${OSMFILE}" "${PBF_URL}"
  record_pbf_size "${OSMFILE}"
}

flatnode_nonempty() {
  [ -n "${FLATNODE_FILE}" ] && [ -f "${FLATNODE_FILE}" ] && [ -s "${FLATNODE_FILE}" ]
}

# Detect --continue checkpoint from DB state (see nominatim_db/tools/database_import.py
# and clicmd/setup.py). Prints one of: done|import-from-file|load-data|indexing|db-postprocess|fresh
detect_continue_at() {
  if [ -n "${NOMINATIM_CONTINUE_AT:-}" ]; then
    case "${NOMINATIM_CONTINUE_AT}" in
      import-from-file | load-data | indexing | db-postprocess)
        echo "${NOMINATIM_CONTINUE_AT}"
        return 0
        ;;
      *)
        log "Invalid NOMINATIM_CONTINUE_AT='${NOMINATIM_CONTINUE_AT}' (allowed: import-from-file|load-data|indexing|db-postprocess)"
        return 1
        ;;
    esac
  fi

  local db_state
  db_state="$(probe_nominatim_db)" || {
    log "Failed to query whether nominatim database exists; refusing fresh/DROP"
    return 1
  }
  if [ "${db_state}" = "missing" ]; then
    echo "fresh"
    return 0
  fi

  local has_place has_placex_rel placex_loaded indexing_started has_pending has_version

  has_place="$(psql_scalar "SELECT COALESCE((SELECT true FROM place LIMIT 1), false)")"
  if ! psql_true "${has_place}"; then
    # No successful osm2pgsql output — safer to let init.sh DROP + re-import.
    echo "fresh"
    return 0
  fi

  # place has rows: after osm2pgsql the next stage is load-data (creates/fills placex).
  # Do NOT auto-select import-from-file — that re-runs osm2pgsql and rebuilds place.
  has_placex_rel="$(psql_scalar "SELECT to_regclass('public.placex') IS NOT NULL")"
  if ! psql_true "${has_placex_rel}"; then
    echo "load-data"
    return 0
  fi

  placex_loaded="$(psql_scalar "SELECT EXISTS (SELECT 1 FROM placex LIMIT 1)")"
  if ! psql_true "${placex_loaded}"; then
    echo "load-data"
    return 0
  fi

  has_version="$(psql_scalar \
    "SELECT EXISTS (SELECT 1 FROM nominatim_properties WHERE property = 'database_version')")"
  if psql_true "${has_version}"; then
    echo "done"
    return 0
  fi

  # indexed_status: 0 = indexed; >0 = pending (load_data insert triggers set 1)
  indexing_started="$(psql_scalar \
    "SELECT EXISTS (SELECT 1 FROM placex WHERE indexed_status = 0 LIMIT 1)")"
  if ! psql_true "${indexing_started}"; then
    # Placex loaded but indexing never committed a row — still in postcodes or pre-index.
    # --continue indexing would skip postcodes; use load-data.
    echo "load-data"
    return 0
  fi

  has_pending="$(psql_scalar \
    "SELECT EXISTS (SELECT 1 FROM placex WHERE indexed_status > 0 LIMIT 1)")"
  if psql_true "${has_pending}"; then
    echo "indexing"
    return 0
  fi

  echo "db-postprocess"
}

# chown project files for the nominatim user without walking the flatnode PVC
# (~100GB under ${PROJECT_DIR}/flatnode).
ensure_project_ownership() {
  local flatnode_dir
  flatnode_dir="$(dirname "${FLATNODE_FILE}")"
  log "Fixing ownership under ${PROJECT_DIR} (excluding ${flatnode_dir})"
  chown nominatim:nominatim "${PROJECT_DIR}"
  find "${PROJECT_DIR}" -mindepth 1 \
    \( -path "${flatnode_dir}" -o -path "${flatnode_dir}/*" \) -prune -o \
    -print0 \
    | xargs -0 -r chown nominatim:nominatim
}

run_continue() {
  local stage="$1"
  ensure_project_ownership

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

  # Match init.sh post-import checks (best-effort index; check-database fails closed on pending indexed_status).
  sudo -E -u nominatim nominatim index --threads "${THREADS}" || true
  sudo -E -u nominatim nominatim admin --check-database
}

mark_finished() {
  touch "${IMPORT_FINISHED}"
  log "Wrote ${IMPORT_FINISHED}"
}

acquire_lock() {
  mkdir -p "$(dirname "${RESUME_LOCK}")"
  # shellcheck disable=SC2094
  exec 9>"${RESUME_LOCK}"
  if ! flock -n 9; then
    log "Another resume-import is already running (lock ${RESUME_LOCK})"
    return 1
  fi
}

release_lock() {
  flock -u 9 2>/dev/null || true
}

finish() {
  local rc="$1"
  stop_postgres
  release_lock
  trap - EXIT
  exit "${rc}"
}

cleanup() {
  stop_postgres
  release_lock
}
trap cleanup EXIT

# Read-only probe for operators/agents: print stage and exit (no lock, no mutation).
if [ "${DETECT_ONLY:-}" = "1" ] || [ "${DETECT_ONLY:-}" = "true" ]; then
  trap - EXIT
  if [ -f "${IMPORT_FINISHED}" ]; then
    echo "done"
    exit 0
  fi
  if [ ! -f "${PGDATA}/PG_VERSION" ]; then
    echo "fresh"
    exit 0
  fi
  if ! pg_isready -q 2>/dev/null; then
    log "Postgres is not ready; cannot detect stage"
    exit 1
  fi
  detect_continue_at
  exit 0
fi

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

acquire_lock
start_postgres
ensure_roles

# Record size of any staging PBF still present so a later emptyDir loss can detect -latest skew.
if [ -f "${OSMFILE}" ] && [ -s "${OSMFILE}" ] && [ ! -f "${PBF_SIZE_MARKER}" ]; then
  record_pbf_size "${OSMFILE}"
fi

stage="$(detect_continue_at)"
log "Detected stage: ${stage}"

case "${stage}" in
  done)
    mark_finished
    finish 0
    ;;
  fresh)
    if flatnode_nonempty; then
      log "Stage is fresh but ${FLATNODE_FILE} is non-empty; refusing init.sh (would DROP DATABASE over stale flatnode)"
      log "Wipe flatnode (task nominatim:reset-for-flatnode) or restore a consistent DB before retrying"
      finish 1
    fi
    log "No resumable import progress; deferring to init.sh"
    finish 2
    ;;
  import-from-file | load-data | indexing | db-postprocess)
    run_continue "${stage}"
    mark_finished
    finish 0
    ;;
  *)
    log "Unhandled stage '${stage}'"
    finish 1
    ;;
esac
