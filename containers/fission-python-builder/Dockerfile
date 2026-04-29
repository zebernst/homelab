# syntax=docker/dockerfile:1
FROM ghcr.io/fission/python-builder:1.34.2
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv
COPY --chmod=755 <<'EOF' /usr/local/bin/build
#!/bin/sh
set -e
if [ -f "${SRC_PKG}/pyproject.toml" ]; then
    uv pip compile "${SRC_PKG}/pyproject.toml" -o /tmp/requirements.txt
    uv pip install --no-cache --link-mode=copy -r /tmp/requirements.txt -t "${SRC_PKG}"
elif [ -f "${SRC_PKG}/requirements.txt" ]; then
    uv pip install --no-cache --link-mode=copy -r "${SRC_PKG}/requirements.txt" -t "${SRC_PKG}"
fi
cp -r "${SRC_PKG}" "${DEPLOY_PKG}"
chmod -R a+rw "${DEPLOY_PKG}"
EOF
