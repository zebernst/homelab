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

STAGING_DIR="/import-staging"
PROJECT_DIR="${PROJECT_DIR:-/nominatim}"
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
if [ -f "${OSMFILE}" ]; then
  REMOTE_SIZE="$(curl -fsIL "${PBF_URL}" | grep -Fi 'content-length:' | tail -n1 | sed 's/.*:[[:space:]]*//' | tr -d '\r')"
  LOCAL_SIZE="$(stat -c %s "${OSMFILE}")"
  if [ -n "${REMOTE_SIZE}" ] && [ "${LOCAL_SIZE}" -gt "${REMOTE_SIZE}" ]; then
    echo "Removing stale OSM extract (${LOCAL_SIZE} bytes > remote ${REMOTE_SIZE} bytes): ${OSMFILE}"
    rm -f "${OSMFILE}"
  fi
fi

exec /app/start.sh
