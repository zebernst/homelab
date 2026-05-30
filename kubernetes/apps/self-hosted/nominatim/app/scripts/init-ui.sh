#!/bin/sh
set -uo pipefail

VERSION="${NOMINATIM_UI_VERSION:?NOMINATIM_UI_VERSION is required}"
UI_ROOT="${UI_ROOT:-/ui-www}"

apk add --no-cache curl tar

mkdir -p "${UI_ROOT}"

curl -fsSL -o /tmp/nominatim-ui.tar.gz \
  "https://github.com/osm-search/nominatim-ui/releases/download/v${VERSION}/nominatim-ui-${VERSION}.tar.gz"

tar -xzf /tmp/nominatim-ui.tar.gz -C /tmp
cp -a "/tmp/nominatim-ui-${VERSION}/dist/." "${UI_ROOT}/"

mkdir -p "${UI_ROOT}/theme"
cat > "${UI_ROOT}/theme/config.theme.js" <<'EOF'
Nominatim_Config.Nominatim_API_Endpoint = '/';
EOF

rm -rf /tmp/nominatim-ui.tar.gz "/tmp/nominatim-ui-${VERSION}"
