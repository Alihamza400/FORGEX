<p align="center">
  <h1 align="center">FORGEX</h1>
  <p align="center">
    <em>Self-hosted multi-agent AI platform. Every stage runs on your infrastructure.</em>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> •
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#cli">CLI</a> •
    <a href="#api">API</a> •
    <a href="#deployment">Deployment</a>
  </p>
</p>

---

## Overview

FORGEX is a production-ready platform for building, orchestrating, and deploying multi-agent AI systems entirely on your own infrastructure. It gives you full control over every layer — LLM inference, vector memory, object storage, authentication, observability, and orchestration — with no data ever leaving your environment.

## Features

- **Multi-Agent Orchestration** — Decompose complex tasks into sub-tasks, dispatch to specialized agents via sequential, parallel, or supervisor strategies
- **Local LLM Integration** — Built-in Ollama client for running models like Llama 3, Mistral, Qwen, and CodeLlama on-premises
- **MCP Tool System** — Extensible Model Context Protocol for registering built-in and external tools
- **Vector Memory** — Qdrant-based semantic memory for agents to recall past interactions
- **RBAC Auth** — JWT and API-Key authentication with 4 roles and 20+ granular permissions
- **Full Observability** — Prometheus metrics, OpenTelemetry tracing, Grafana dashboards, structured logging
- **REST API + CLI + UI** — Three interfaces for managing agents, running orchestrations, and monitoring
- **Kubernetes Native** — Helm chart, K8s manifests, HPA, PDB, network policies, resource quotas
- **Docker Compose Stack** — 11 integrated services (Postgres, Redis, Qdrant, MinIO, Ollama, Prometheus, Grafana, Tempo, OpenTelemetry)

## Architecture

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│    CLI      │  │    API      │  │     UI      │
│  (Typer)    │  │  (FastAPI)  │  │  (React)    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────┬───┴────────────────┘
                    │
           ┌────────▼────────┐
           │  Orchestrator   │
           │  ┌──────────┐   │
           │  │  Planner │   │
           │  │Coordinator│  │
           │  │ Supervisor│  │
           │  └──────────┘   │
           └────────┬────────┘
                    │
      ┌─────────────┼─────────────┐
      │             │             │
┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
│  Agent 1  │ │ Agent 2 │ │ Agent N   │
│ (Runtime) │ │(Runtime) │ │ (Runtime) │
└─────┬─────┘ └────┬────┘ └─────┬─────┘
      │             │             │
      └─────────────┼─────────────┘
                    │
           ┌────────▼────────┐
           │   ToolRegistry  │
           │ (Built-in + MCP)│
           └────────┬────────┘
                    │
   ┌────────┬───────┼───────┬────────┬────────┐
   │        │       │       │        │        │
┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌───▼───┐ ┌──▼──┐
│LLM  │ │Memory│ │State│ │Storage│ │Auth   │ │Obs  │
│Ollama│ │Qdrant│ │Redis│ │MinIO │ │JWT/RBAC│ │Prom+│
└─────┘ └─────┘ └─────┘ └──────┘ └───────┘ │Graf │
                                            └─────┘
```

### Package Structure

| Package | Description |
|---|---|
| `packages/core/forge/` | Core library — auth, llm (Ollama), memory (Qdrant), orchestrator, runtime, tools (MCP), state (Redis), storage (MinIO/Postgres), observability |
| `packages/api/forge/api/` | FastAPI REST server (`:8000`) — agent management, orchestration, auth, health |
| `packages/cli/forge/cli/` | Typer CLI — `forge run`, `orchestrate`, `build`, `deploy`, `stack` management |
| `packages/ui/` | React 19 + Vite 6 + Tailwind v4 dashboard |
| `packages/deploy/` | Docker Compose, Helm chart, K8s manifests, monitoring configs |
| `packages/server-mcp/` | External MCP server implementations |

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for infrastructure services)
- [Ollama](https://ollama.ai/) (for local LLM inference)

### 1. Install the CLI

```bash
pip install forge-cli
```

Or with `uv`:

```bash
uv tool install forge-cli
```

Verify it works:

```bash
forge version
```

### 2. Configure

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

### 3. Start Infrastructure

```bash
make docker-up
```

This starts Postgres, Redis, Qdrant, MinIO, Ollama, Prometheus, Grafana, Tempo, and exporters.

### 4. Run the API

```bash
make dev-api
```

The API is now available at `http://localhost:8000`.

### 5. Use the CLI

```bash
# Run a single agent
forge run config/agent.example.yaml --task "Summarize the latest AI research"

# Multi-agent orchestration
forge orchestrate "Build a web application" \
  --agent examples/research-agent.yaml \
  --agent examples/support-bot.yaml \
  --strategy sequential
```

## CLI

### Install

```bash
pip install forge-cli
# or
uv tool install forge-cli
```

The `forge` CLI provides full control over agents, orchestrations, deployments, and infrastructure.

| Command | Description |
|---|---|
| `forge version` | Show version |
| `forge status` | Show stack service status |
| `forge validate <config>` | Validate an agent YAML/JSON config |
| `forge run <config> --task <task>` | Run a single agent with a task |
| `forge orchestrate <task> --agent <config>` | Run multi-agent orchestration |
| `forge build <config> --tag <tag>` | Build a Docker image for an agent |
| `forge deploy <config> --namespace <ns>` | Deploy an agent to Kubernetes |
| `forge up [--detach]` | Start the local Docker Compose stack |
| `forge down [--volumes]` | Stop the local stack |
| `forge logs [--follow]` | Show stack logs |
| `forge ps` | List stack containers |
| `forge auth login` | Authenticate with the API |

### Orchestration Strategies

| Strategy | Description |
|---|---|
| `sequential` | Sub-tasks execute in dependency order |
| `parallel` | Independent sub-tasks execute concurrently |
| `supervisor` | A supervising LLM delegates, reviews, and consolidates results |
| `auto` | Automatically selects the best strategy based on task structure |

## API

The REST API is documented automatically at `http://localhost:8000/docs` (Swagger UI) when running.

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/readyz`, `/livez` | Health checks |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/api/v1/auth/login` | JWT login |
| `POST` | `/api/v1/auth/refresh` | Refresh token |
| `GET` | `/api/v1/agents` | List agents |
| `POST` | `/api/v1/agents/run` | Run a single agent |
| `POST` | `/api/v1/agents/validate` | Validate agent config |
| `POST` | `/api/v1/orchestrate` | Execute orchestration |
| `GET` | `/api/v1/orchestrate/{id}` | Get orchestration result |

### Authentication

- Bearer JWT (HS256) or X-API-Key header
- RBAC with 4 roles: `admin`, `operator`, `developer`, `viewer`
- 20+ granular permissions (e.g., `agent:create`, `orchestrate:execute`, `deploy:manage`)

## UI Dashboard

The React dashboard provides a visual interface for managing agents, running orchestrations, and monitoring performance.

```bash
make ui-dev    # Start at http://localhost:5173
```

Pages: Dashboard, Agents, Agent Detail, Orchestrate, Logs, Settings, Login, Register.

## Configuration

### Agent Configuration

Agents are defined in YAML files:

```yaml
name: research-agent
role: Research Analyst
goal: Gather and synthesize information from multiple sources
model:
  provider: ollama
  name: llama3.2:3b
tools:
  - web_search
  - read_file
  - calculator
memory:
  type: qdrant
  collection: research_memories
max_iterations: 10
```

### Environment Variables

All settings are configurable via environment variables with the `FORGE_` prefix:

| Variable | Default | Description |
|---|---|---|
| `FORGE_API_HOST` | `0.0.0.0` | API bind address |
| `FORGE_API_PORT` | `8000` | API port |
| `FORGE_API_SECRET_KEY` | — | JWT signing key (empty = auth disabled) |
| `DATABASE_URL` | `postgresql+asyncpg://forge:forge_secret@localhost:5432/forge` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO S3 endpoint |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `FORGE_DEFAULT_MODEL` | `llama3.2:3b` | Default LLM model |
| `FORGE_LOG_LEVEL` | `INFO` | Log level |
| `FORGE_OTLP_ENDPOINT` | — | OpenTelemetry endpoint |

## Docker Services

FORGEX runs 11 integrated Docker services via Docker Compose:

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | postgres:16 | 5432 | Primary database |
| `redis` | redis:7-alpine | 6379 | State & caching |
| `qdrant` | qdrant/qdrant:v1.12.0 | 6333 | Vector memory |
| `minio` | minio/minio:latest | 9000 | Object storage |
| `ollama` | ollama/ollama:latest | 11434 | LLM inference |
| `prometheus` | prom/prometheus:v2.53.0 | 9090 | Metrics |
| `grafana` | grafana/grafana:11.3.0 | 3000 | Dashboards |
| `tempo` | grafana/tempo:2.6.0 | 3200 | Distributed tracing |
| `otel-collector` | otel/opentelemetry-collector-contrib:0.108.0 | 4317 | Trace collection |
| `postgres-exporter` | prometheuscommunity/postgres-exporter:v0.15.0 | 9187 | DB metrics |
| `redis-exporter` | oliver006/redis_exporter:v1.62.0 | 9121 | Redis metrics |

## Deployment

### Docker Compose (local / single-host)

```bash
make docker-up
```

### Kubernetes

```bash
# Using Helm
make helm-install

# Using raw manifests
kubectl apply -f packages/deploy/k8s/
```

The Helm chart includes: agent & API deployments, Postgres/Redis/Qdrant/MinIO/Ollama statefulsets, HPA, PDB, network policies, resource quotas, secrets, Prometheus rules, and Grafana dashboards.

## Development

```bash
# Install all packages
make install

# Lint & typecheck
make lint
make typecheck

# Run tests
make test-unit          # 155 unit tests (no deps)
make test-integration   # 35 integration tests (Docker required)
make test-e2e           # 5 end-to-end tests (full stack)
make test-benchmark     # 3 benchmark tests

# Run with coverage
make test-cov
```

### Code Conventions

- Python 3.12+, async everywhere
- Ruff linting (line-length=100, double quotes)
- mypy strict mode
- All datetimes: naive UTC
- MCP protocol for all tool interfaces

## Project Structure

```
FORGEX/
├── packages/
│   ├── core/forge/           # Core library
│   │   ├── auth/             # JWT, RBAC, API keys
│   │   ├── core/             # Config, agent config, secrets vault
│   │   ├── llm/              # Ollama client
│   │   ├── memory/           # Qdrant vector memory
│   │   ├── observability/    # Metrics, tracing, logging
│   │   ├── orchestrator/     # Planner, coordinator, supervisor, registry
│   │   ├── runtime/          # Agent runtime, task loop
│   │   ├── state/            # Redis state management
│   │   ├── storage/          # MinIO, Postgres repository
│   │   └── tools/            # Tool registry, built-in tools, MCP client
│   ├── api/forge/api/        # FastAPI REST server
│   ├── cli/forge/cli/        # Typer CLI
│   ├── ui/                   # React + Vite dashboard
│   ├── deploy/               # Docker Compose, Helm, K8s, monitoring
│   └── server-mcp/           # External MCP servers
├── tests/
│   ├── unit/                 # 14 test files
│   ├── integration/          # Integration tests
│   ├── e2e/                  # End-to-end tests
│   └── benchmarks/           # Performance benchmarks
├── config/                   # Example agent configs
├── examples/                 # Example agent YAML files
├── scripts/                  # Utility scripts
├── .env.example
├── Makefile
├── AGENTS.md
└── pyproject.toml
```

## License

MIT
