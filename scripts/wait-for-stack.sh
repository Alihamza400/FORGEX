#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for Forge stack to become healthy..."

MAX_RETRIES=30
SLEEP=5

services=(
    "postgres:5432"
    "qdrant:6333"
    "redis:6379"
    "minio:9000"
    "ollama:11434"
)

for svc in "${services[@]}"; do
    host="${svc%%:*}"
    port="${svc##*:}"
    retries=0
    while ! nc -z "$host" "$port" 2>/dev/null; do
        retries=$((retries + 1))
        if [ "$retries" -ge "$MAX_RETRIES" ]; then
            echo "ERROR: $host:$port not reachable after $MAX_RETRIES attempts"
            exit 1
        fi
        echo "Waiting for $host:$port... (attempt $retries/$MAX_RETRIES)"
        sleep "$SLEEP"
    done
    echo "OK: $host:$port is reachable"
done

echo "All services are healthy!"
