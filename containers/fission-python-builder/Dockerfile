# syntax=docker/dockerfile:1
FROM ghcr.io/fission/python-builder:v1.22.0
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'if [ -f "${SRC_PKG}/pyproject.toml" ]; then' \
    '    uv pip install --no-cache "${SRC_PKG}" -t "${SRC_PKG}"' \
    'elif [ -f "${SRC_PKG}/requirements.txt" ]; then' \
    '    uv pip install --no-cache -r "${SRC_PKG}/requirements.txt" -t "${SRC_PKG}"' \
    'fi' \
    > /build && chmod +x /build
