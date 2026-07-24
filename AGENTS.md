# Forge — Multi-Agent AI Platform

## Overview
Self-hosted platform for building and deploying multi-agent AI systems. Every stage (LLM, build, deploy, state, memory, storage, auth, monitoring) runs on your infrastructure.

## Project Structure
```
pyproject.toml          # Root workspace (uv)
packages/
  core/forge/           # forge-core: core library
    auth/               # Auth models, service, RBAC, JWT, rate limiting
    core/               # Config, logging, secrets vault
    llm/                # Ollama client interface
    memory/             # Qdrant vector memory manager
    observability/      # Metrics, tracing, logging
    orchestrator/       # Multi-agent orchestration (planner, coordinator)
    runtime/            # Agent runtime, task loop, MCP tool system
    state/              # Redis state management
    storage/            # MinIO object storage
    tools/              # Built-in tools (calculator, filesystem, etc.)
  api/forge/api/        # forge-api: FastAPI REST server
  cli/forge/cli/        # forge-cli: CLI (Typer)
  deploy/               # Docker Compose, Helm chart, K8s manifests, monitoring configs
  ui/                   # React + Vite + Tailwind v4 dashboard
  server-mcp/           # External MCP servers
tests/
  unit/                 # 14 test files, 155 unit tests (no deps)
  integration/          # 35 tests (need Docker services)
  e2e/                  # 5 end-to-end tests (full stack)
  benchmarks/           # 3 pytest-benchmark tests
```

## Key Commands
```bash
make install            # uv sync --all-packages
make dev-api            # Start API on :8000
make lint               # ruff check
make typecheck          # mypy strict mode
make test               # all pytest
make test-unit          # 155 unit tests (no deps)
make test-integration   # integration tests (Docker required)
make test-e2e           # e2e tests (full stack)
make test-benchmark     # benchmark tests (API must be running)
make test-cov           # tests with coverage
make docker-up          # Start all 11 Docker services
make docker-down        # Stop all Docker services
```

## Code Conventions
- Python 3.12+, uv workspace with hatchling build
- Namespace: `forge-core` owns `forge.*`, `forge-api`/`forge-cli` extend it
- All datetimes: naive UTC (`datetime.now(UTC).replace(tzinfo=None)`)
- Async everywhere (asyncio, asyncpg, httpx)
- MCP protocol for all tool interfaces
- Ruff lint (line-length=100, double quotes), mypy strict
- Tests use pytest with markers: `unit`, `integration`, `e2e`, `benchmark`

## Architecture
- API runs on host (:8000), proxied via Vite from UI (:5173)
- Docker services: postgres, redis, qdrant, minio, ollama, prometheus, grafana, tempo, otel-collector, postgres-exporter, redis-exporter
- Auth: Bearer JWT (HS256) or X-API-Key, RBAC with 4 roles and 20+ permissions
- DB tables auto-create on API startup via `create_all()`
- Health check pings all 5 core services with latency
- All services run on host networking from Docker perspective
