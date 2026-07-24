.PHONY: install dev lint typecheck test clean ui-dev ui-build \
	docker-up docker-down docker-logs docker-ps \
	build-agent build-api deploy-agent deploy-stack helm-install helm-lint \
	sbom sign trivy backup restore gen-certs \
	mon-up mon-down mon-logs grafana prometheus tempo

# === Python ===
install:
	uv sync --all-packages

dev-api:
	uv run --package forge-api uvicorn forge.api.main:app --reload --host 0.0.0.0 --port 8000

dev-cli:
	uv run --package forge-cli forge --help

# === Quality ===
lint:
	uv run ruff check packages/ tests/

lint-fix:
	uv run ruff check --fix packages/ tests/

typecheck:
	uv run mypy packages/ tests/

# === Testing ===
test:
	uv run pytest

test-unit:
	uv run pytest -m unit

test-integration:
	uv run pytest -m integration -v

test-e2e:
	uv run pytest -m e2e -v

test-benchmark:
	uv run pytest -m benchmark -v

test-cov:
	uv run pytest --cov

test-all:
	uv run pytest -m "unit or integration" --cov

# === UI ===
ui-install:
	cd packages/ui && npm install

ui-dev:
	cd packages/ui && npm run dev

ui-build:
	cd packages/ui && npm run build

# === Docker ===
docker-up:
	docker compose -f packages/deploy/docker-compose.yml --env-file .env up -d

docker-down:
	docker compose -f packages/deploy/docker-compose.yml --env-file .env down

docker-logs:
	docker compose -f packages/deploy/docker-compose.yml logs -f

docker-ps:
	docker compose -f packages/deploy/docker-compose.yml ps

# === Build (Docker images) ===
build-agent:
	@echo "Usage: make build-agent CONFIG=path/to/agent.yaml [TAG=tag]"
	uv run --package forge-cli forge build $(CONFIG) $(if $(TAG),--tag $(TAG))

build-api:
	docker build -f packages/deploy/docker/api.Dockerfile -t forge/api:latest .

# === SBOM & Security Scanning ===
sbom:
	@echo "Generating SBOM with syft..."
	syft packages/deploy/docker/api.Dockerfile -o spdx-json=forge-api.sbom.spdx.json
	syft packages/deploy/docker/agent.Dockerfile -o spdx-json=forge-agent.sbom.spdx.json

trivy:
	@echo "Scanning images with trivy..."
	trivy image --severity CRITICAL,HIGH forge/api:latest
	trivy image --severity CRITICAL,HIGH forge/agent:latest

sign:
	@echo "Signing images with cosign..."
	cosign sign --key env://COSIGN_PRIVATE_KEY forge/api:latest
	cosign sign --key env://COSIGN_PRIVATE_KEY forge/agent:latest

# === Deploy (Kubernetes) ===
deploy-agent:
	@echo "Usage: make deploy-agent CONFIG=path/to/agent.yaml [NAMESPACE=forge]"
	uv run --package forge-cli forge deploy $(CONFIG) $(if $(NAMESPACE),--namespace $(NAMESPACE))

deploy-stack:
	uv run --package forge-cli forge deploy stack $(if $(NAMESPACE),--namespace $(NAMESPACE))

# === Helm ===
helm-install:
	helm upgrade --install forge packages/deploy/helm/forge/ \
		--namespace forge --create-namespace \
		$(if $(VALUES),--values $(VALUES)) \
		$(if $(SET),--set $(SET))

helm-lint:
	helm lint packages/deploy/helm/forge/

helm-template:
	helm template forge packages/deploy/helm/forge/ --namespace forge

helm-uninstall:
	helm uninstall forge --namespace forge

# === Backup & Restore ===
backup:
	@echo "Running forge-backup..."
	packages/deploy/scripts/backup.sh

restore:
	@echo "Usage: make restore BACKUP=<backup-path>"
	packages/deploy/scripts/restore.sh $(BACKUP)

# === TLS Certificates ===
gen-certs:
	@echo "Generating development TLS certificates..."
	packages/deploy/scripts/gen-certs.sh

# === Monitoring ===
mon-up:
	docker compose -f packages/deploy/docker-compose.yml --env-file .env up -d prometheus grafana otel-collector tempo postgres-exporter redis-exporter

mon-down:
	docker compose -f packages/deploy/docker-compose.yml --env-file .env down prometheus grafana otel-collector tempo postgres-exporter redis-exporter

mon-logs:
	docker compose -f packages/deploy/docker-compose.yml --env-file .env logs -f prometheus grafana otel-collector tempo

grafana:
	@echo "Grafana: http://localhost:3000 (admin:forge)"

prometheus:
	@echo "Prometheus: http://localhost:9090"

tempo:
	@echo "Tempo: http://localhost:3200"

# === Clean ===
clean:
	rm -rf .venv/ __pycache__/ .pytest_cache/ .ruff_cache/ .mypy_cache/
	rm -rf packages/*/dist/ packages/*/*.egg-info/
	rm -rf *.sbom.spdx.json certs/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
