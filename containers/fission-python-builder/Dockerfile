# syntax=docker/dockerfile:1
FROM ghcr.io/fission/python-builder:v1.22.0
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN printf '#!/bin/sh\nset -e\n[ -f "${SRC_PKG}/requirements.txt" ] && uv pip install --no-cache -r "${SRC_PKG}/requirements.txt" -t "${SRC_PKG}"\n' \
    > /build && chmod +x /build
