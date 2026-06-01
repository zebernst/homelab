#!/bin/bash
set -euo pipefail

DOWNURL="${NOMINATIM_DOWNURL:-https://download.geofabrik.de}"
PROJECT_DIR="${PROJECT_DIR:-/nominatim}"
IMPORTED_LIST="${PROJECT_DIR}/imported-regions.txt"
IMPORT_STAGING="${IMPORT_STAGING:-/import-staging}"
IMPORT_FINISHED="${IMPORT_FINISHED:-/var/lib/postgresql/16/main/import-finished}"
CURL_USER_AGENT="${USER_AGENT:-nominatim-maintenance}"
ALLOW_REGION_IMPORT="${NOMINATIM_ALLOW_REGION_IMPORT:-false}"
IMPORT_MAX_REGIONS="${NOMINATIM_IMPORT_MAX_REGIONS:-1}"
IMPORT_ONLY_REGION="${NOMINATIM_IMPORT_ONLY_REGION:-}"
SKIP_INCREMENTAL="${NOMINATIM_SKIP_INCREMENTAL:-false}"

truthy() {
  case "${1,,}" in
    true | 1 | yes | on) return 0 ;;
    *) return 1 ;;
  esac
}

if [ -z "${NOMINATIM_REGIONS:-}" ]; then
  echo "[nominatim-maintenance] NOMINATIM_REGIONS is not set; exiting."
  exit 1
fi

mapfile -t DESIRED_REGIONS < <(
  echo "${NOMINATIM_REGIONS}" | tr ',' ' ' | tr ' ' '\n' | sed '/^[[:space:]]*$/d'
)

if [ "${#DESIRED_REGIONS[@]}" -eq 0 ]; then
  echo "[nominatim-maintenance] No regions configured; exiting."
  exit 0
fi

if [ -n "${IMPORT_ONLY_REGION}" ]; then
  region_known=false
  for region in "${DESIRED_REGIONS[@]}"; do
    if [ "${region}" = "${IMPORT_ONLY_REGION}" ]; then
      region_known=true
      break
    fi
  done
  if [ "${region_known}" = "false" ]; then
    echo "[nominatim-maintenance] NOMINATIM_IMPORT_ONLY_REGION=${IMPORT_ONLY_REGION} is not listed in NOMINATIM_REGIONS."
    exit 1
  fi
fi

mkdir -p "${IMPORT_STAGING}" "${PROJECT_DIR}/update"

if [ ! -f "${IMPORT_FINISHED}" ]; then
  echo "[nominatim-maintenance] Import not finished (${IMPORT_FINISHED} missing); skipping maintenance."
  exit 0
fi

if ! sudo -u postgres pg_isready -q 2>/dev/null; then
  echo "[nominatim-maintenance] PostgreSQL is not ready; exiting."
  exit 1
fi

if [ -d /nominatim/flatnode ] && { [ ! -f /nominatim/flatnode/flatnode.file ] || [ ! -s /nominatim/flatnode/flatnode.file ]; }; then
  echo "[nominatim-maintenance] WARNING: flatnode volume is mounted but flatnode.file is missing or empty."
  echo "[nominatim-maintenance] Large add-data imports need flatnode configured at initial import; see Nominatim docs."
fi

seed_state() {
  local region="$1"
  local state_dir="${PROJECT_DIR}/update/${region}"
  mkdir -p "${state_dir}"
  curl -fsSL "${DOWNURL}/${region}-updates/state.txt" > "${state_dir}/sequence.state"
}

if [ ! -f "${IMPORTED_LIST}" ]; then
  touch "${IMPORTED_LIST}"
  BASE_REGION="${DESIRED_REGIONS[0]}"
  echo "[nominatim-maintenance] Seeding imported list with base region ${BASE_REGION}"
  echo "${BASE_REGION}" >> "${IMPORTED_LIST}"
  seed_state "${BASE_REGION}"
fi

import_new_regions() {
  if ! truthy "${ALLOW_REGION_IMPORT}"; then
    local missing=()
    for region in "${DESIRED_REGIONS[@]}"; do
      if ! grep -qxF "${region}" "${IMPORTED_LIST}"; then
        missing+=("${region}")
      fi
    done
    if [ "${#missing[@]}" -gt 0 ]; then
      echo "[nominatim-maintenance] Skipping full PBF import for ${#missing[@]} region(s) (set NOMINATIM_ALLOW_REGION_IMPORT=true for controlled imports)."
      printf '  - %s\n' "${missing[@]}"
      echo "[nominatim-maintenance] Add regions manually or enable imports with a low NOMINATIM_IMPORT_MAX_REGIONS; do not run multi-GB add-data from the daily cron."
    fi
    return 0
  fi

  local imported=0
  for region in "${DESIRED_REGIONS[@]}"; do
    if [ -n "${IMPORT_ONLY_REGION}" ] && [ "${region}" != "${IMPORT_ONLY_REGION}" ]; then
      continue
    fi
    if grep -qxF "${region}" "${IMPORTED_LIST}"; then
      if [ -n "${IMPORT_ONLY_REGION}" ] && [ "${region}" = "${IMPORT_ONLY_REGION}" ]; then
        echo "[nominatim-maintenance] Region ${IMPORT_ONLY_REGION} is already imported."
        exit 0
      fi
      continue
    fi
    if [ "${imported}" -ge "${IMPORT_MAX_REGIONS}" ]; then
      echo "[nominatim-maintenance] Reached NOMINATIM_IMPORT_MAX_REGIONS=${IMPORT_MAX_REGIONS}; deferring remaining regions."
      break
    fi

    import_file="${IMPORT_STAGING}/$(echo "${region}" | tr '/' '-')-latest.osm.pbf"
    echo "[nominatim-maintenance] Importing new region ${region}"
    curl -L -A "${CURL_USER_AGENT}" --fail-with-body \
      "${DOWNURL}/${region}-latest.osm.pbf" -o "${import_file}"
    sudo -E -u nominatim nominatim add-data --project-dir "${PROJECT_DIR}" --file "${import_file}"
    seed_state "${region}"
    echo "${region}" >> "${IMPORTED_LIST}"
    rm -f "${import_file}"
    imported=$((imported + 1))
    CHANGED=true
  done
}

CHANGED=false
import_new_regions

if ! truthy "${SKIP_INCREMENTAL}"; then
  for region in "${DESIRED_REGIONS[@]}"; do
    if ! grep -qxF "${region}" "${IMPORTED_LIST}"; then
      continue
    fi

    state_file="${PROJECT_DIR}/update/${region}/sequence.state"
    if [ ! -f "${state_file}" ]; then
      echo "[nominatim-maintenance] Missing state for ${region}; seeding and continuing."
      seed_state "${region}"
      continue
    fi

    changes_file="${IMPORT_STAGING}/changes-$(echo "${region}" | tr '/' '-').osc.gz"
    echo "[nominatim-maintenance] Fetching changes for ${region}"
    if pyosmium-get-changes \
        --server "${DOWNURL}/${region}-updates/" \
        --state-file "${state_file}" \
        -o "${changes_file}" 2>/dev/null && [ -s "${changes_file}" ]; then
      sudo -E -u nominatim nominatim add-data \
        --project-dir "${PROJECT_DIR}" \
        --diff "${changes_file}"
      CHANGED=true
    fi
    rm -f "${changes_file}"
  done
fi

if [ "${CHANGED}" = "true" ]; then
  echo "[nominatim-maintenance] Re-indexing after import/update cycle."
  sudo -E -u nominatim nominatim index --project-dir "${PROJECT_DIR}"
else
  echo "[nominatim-maintenance] No new data found."
fi
