from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from forge.core.agent_config import AgentConfig
from forge.core.logging import get_logger

logger = get_logger("forge.core.config_loader")


class ConfigLoadError(Exception):
    pass


def load_agent_config(path: str | Path) -> AgentConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigLoadError(f"Config file not found: {path}")
    if not path.is_file():
        raise ConfigLoadError(f"Path is not a file: {path}")

    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e
    elif path.suffix in (".json",):
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"Invalid JSON in {path}: {e}") from e
    else:
        raise ConfigLoadError(
            f"Unsupported config format: {path.suffix}. Use .yaml, .yml, or .json"
        )

    if not isinstance(data, dict):
        raise ConfigLoadError(f"Config must be a YAML/JSON object, got {type(data).__name__}")

    try:
        config = AgentConfig.model_validate(data)
    except Exception as e:
        raise ConfigLoadError(f"Config validation failed: {e}") from e

    logger.info("loaded agent config", name=config.name, role=config.role)
    return config
