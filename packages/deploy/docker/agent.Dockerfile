# syntax=docker/dockerfile:1
# forge-agent — hardened multi-stage non-root production container
# Build: docker build -f packages/deploy/docker/agent.Dockerfile \
#   --build-arg AGENT_CONFIG=./config/agent.example.yaml \
#   -t forge/agent-name:tag .

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY packages/cli/pyproject.toml packages/cli/
COPY packages/core/forge/ packages/core/forge/
COPY packages/cli/forge/ packages/cli/forge/

RUN uv sync --frozen --no-dev && uv build --wheel --out-dir /build/dist

FROM python:3.12-slim

RUN groupadd -r forge && useradd -r -g forge -d /var/lib/forge -s /sbin/nologin forge \
    && mkdir -p /var/lib/forge /etc/forge \
    && chown -R forge:forge /var/lib/forge /etc/forge

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /bin/sh /bin/bash /bin/dash

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

COPY packages/deploy/docker/agent-entrypoint.sh /usr/local/bin/agent-entrypoint.sh
RUN chmod +x /usr/local/bin/agent-entrypoint.sh

USER forge
WORKDIR /var/lib/forge

ARG AGENT_CONFIG=./config/agent.example.yaml
COPY ${AGENT_CONFIG} /etc/forge/config.yaml

EXPOSE 8080

LABEL org.opencontainers.image.source="https://github.com/Alihamza400/FORGEX" \
      org.opencontainers.image.description="Forge Agent Runtime" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="0.1.0"

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD forge version > /dev/null 2>&1 || exit 1

ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
CMD ["--help"]
