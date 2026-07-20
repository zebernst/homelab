# syntax=docker/dockerfile:1
# Code-only image for Fission OCI packages (runtime comes from the Environment).
# Layout matches an extracted deployment archive: deps + entrypoint at /.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY main.py calendars.py ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --no-emit-project -o requirements.txt \
    && mkdir -p /out \
    && uv pip install --no-cache --target=/out -r requirements.txt \
    && cp main.py calendars.py /out/

FROM scratch
COPY --from=build /out/ /
