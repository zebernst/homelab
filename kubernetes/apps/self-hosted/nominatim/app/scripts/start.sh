#!/bin/bash
set -uo pipefail
if [ "${DEBUG:-}" = "true" ] || [ "${DEBUG:-}" = "1" ]; then
  set -e
fi

FIRST_REGION="$(printf '%s\n' "${NOMINATIM_REGIONS}" | tr ',[:space:]' '\n' | sed '/^[[:space:]]*$/d' | awk 'NR==1 { print; exit }')"
if [ -z "${FIRST_REGION}" ]; then
  echo "NOMINATIM_REGIONS must include at least one region"
  exit 1
fi
export PBF_URL="${NOMINATIM_DOWNURL:-https://download.geofabrik.de}/${FIRST_REGION}-latest.osm.pbf"

STAGING_DIR="${IMPORT_STAGING:-/import-staging}"
PROJECT_DIR="${PROJECT_DIR:-/nominatim}"
PGDATA="${PGDATA:-/var/lib/postgresql/16/main}"
IMPORT_FINISHED="${IMPORT_FINISHED:-${PGDATA}/import-finished}"
mkdir -p "${STAGING_DIR}"

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

OSMFILE="${STAGING_DIR}/data.osm.pbf"
PBF_SIZE_MARKER="${PBF_SIZE_MARKER:-${PROJECT_DIR}/.bootstrap-pbf-bytes}"
if [ -f "${OSMFILE}" ]; then
  REMOTE_SIZE="$(curl -fsIL --connect-timeout 30 --max-time 120 "${PBF_URL}" | grep -Fi 'content-length:' | tail -n1 | sed 's/.*:[[:space:]]*//' | tr -d '\r')"
  LOCAL_SIZE="$(stat -c %s "${OSMFILE}")"
  if [ -n "${REMOTE_SIZE}" ] && [ "${LOCAL_SIZE}" -gt "${REMOTE_SIZE}" ]; then
    echo "Removing stale OSM extract (${LOCAL_SIZE} bytes > remote ${REMOTE_SIZE} bytes): ${OSMFILE}"
    rm -f "${OSMFILE}"
  elif [ -s "${OSMFILE}" ]; then
    # Persist size on the project PVC so resume can refuse a skewed -latest re-download after emptyDir loss.
    mkdir -p "$(dirname "${PBF_SIZE_MARKER}")"
    printf '%s\n' "${LOCAL_SIZE}" > "${PBF_SIZE_MARKER}"
  fi
fi

# If pgdata exists but bootstrap never wrote import-finished, resume instead of
# letting /app/init.sh DROP DATABASE and wipe osm2pgsql progress.
if [ ! -f "${IMPORT_FINISHED}" ] && [ -f "${PGDATA}/PG_VERSION" ]; then
  # config.sh writes PROJECT_DIR/.env (flatnode, replication, style) needed by nominatim.
  /app/config.sh
  resume_rc=0
  /scripts/resume-import.sh || resume_rc=$?
  case "${resume_rc}" in
    0)
      echo "[nominatim] Resume completed; starting API"
      ;;
    2)
      echo "[nominatim] No resumable import progress; continuing with mediagis init"
      ;;
    *)
      echo "[nominatim] Resume failed (exit ${resume_rc}); refusing to run init.sh (would DROP DATABASE)"
      exit 1
      ;;
  esac
fi

exec /app/start.sh
