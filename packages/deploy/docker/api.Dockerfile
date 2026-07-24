# syntax=docker/dockerfile:1
# forge-api — hardened multi-stage non-root production container
# Build: docker build -f packages/deploy/docker/api.Dockerfile -t forge/api:tag .

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY packages/api/pyproject.toml packages/api/
COPY packages/core/forge/ packages/core/forge/
COPY packages/api/forge/ packages/api/forge/

RUN uv sync --frozen --no-dev && uv build --wheel --out-dir /build/dist

FROM python:3.12-slim

RUN groupadd -r forge && useradd -r -g forge -d /var/lib/forge -s /sbin/nologin forge \
    && mkdir -p /var/lib/forge \
    && chown -R forge:forge /var/lib/forge

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /bin/sh /bin/bash /bin/dash

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER forge
WORKDIR /var/lib/forge

EXPOSE 8000

LABEL org.opencontainers.image.source="https://github.com/forge/forge" \
      org.opencontainers.image.description="Forge API Server" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="0.1.0"

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f --max-time 5 http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "forge.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
