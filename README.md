# FORGEX

A self-hosted platform for building and deploying multi-agent AI systems. Every stage — LLM, build, deploy, state, memory, storage, auth, monitoring — runs on your own infrastructure.

## Architecture

| Package | Description |
|---|---|
| `packages/core/` | Core library: auth, llm (Ollama), memory (Qdrant), orchestrator, runtime, tools (MCP) |
| `packages/api/` | FastAPI REST server on `:8000` |
| `packages/cli/` | Typer CLI (`forge run`, `forge orchestrate`, `forge deploy`) |
| `packages/ui/` | React + Vite + Tailwind dashboard |
| `packages/deploy/` | Docker Compose, Helm chart, K8s manifests, monitoring |

## Quick Start

```bash
make install           # uv sync --all-packages
make dev-api           # Start API on :8000
# or
make docker-up         # Start all 11 Docker services
```

## CLI Usage

```bash
forge run agent.yaml --task "Your task"
forge orchestrate "Complex task" --agent planner.yaml --agent coder.yaml
forge validate agent.yaml
```

## License

MIT
