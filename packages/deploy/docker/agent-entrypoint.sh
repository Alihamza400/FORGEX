#!/bin/sh
# forge-agent entrypoint — supports task via env var or stdin file
set -e

CONFIG_PATH="${FORGE_AGENT_CONFIG:-/etc/forge/config.yaml}"

if [ -n "$FORGE_AGENT_TASK" ]; then
    exec forge run "$CONFIG_PATH" --task "$FORGE_AGENT_TASK"
elif [ -f /etc/forge/task.txt ]; then
    exec forge run "$CONFIG_PATH" --stdin < /etc/forge/task.txt
else
    exec forge "$@"
fi
