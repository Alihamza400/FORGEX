from __future__ import annotations

from pathlib import Path

import pytest
from forge.core.config_loader import ConfigLoadError, load_agent_config


def test_load_yaml(tmp_path: Path):
    config_file = tmp_path / "agent.yaml"
    config_file.write_text("""
name: test-agent
role: helper
goal: help users
model:
  name: llama3.2:3b
  temperature: 0.5
    """.strip())
    config = load_agent_config(config_file)
    assert config.name == "test-agent"
    assert config.role == "helper"
    assert config.model.temperature == 0.5
def test_load_json(tmp_path: Path):
    config_file = tmp_path / "agent.json"
    config_file.write_text("""
{
    "name": "json-agent",
    "role": "analyst",
    "goal": "analyze data",
    "model": {"name": "mixtral:8x7b"}
}
    """.strip())
    config = load_agent_config(config_file)
    assert config.name == "json-agent"
    assert config.model.name == "mixtral:8x7b"
def test_file_not_found():
    with pytest.raises(ConfigLoadError, match="not found"):
        load_agent_config("/nonexistent/path.yaml")
def test_invalid_yaml(tmp_path: Path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("name: broken: yaml: : : :")
    with pytest.raises(ConfigLoadError, match="Invalid YAML"):
        load_agent_config(config_file)
def test_invalid_schema(tmp_path: Path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("name: a\nrole: r\n")
    with pytest.raises(ConfigLoadError, match="goal"):
        load_agent_config(config_file)
def test_unsupported_format(tmp_path: Path):
    config_file = tmp_path / "agent.toml"
    config_file.write_text("[agent]\nname = 'test'")
    with pytest.raises(ConfigLoadError, match="Unsupported"):
        load_agent_config(config_file)
def test_not_a_dict(tmp_path: Path):
    config_file = tmp_path / "list.yaml"
    config_file.write_text("- item1\n- item2")
    with pytest.raises(ConfigLoadError, match="must be a YAML/JSON object"):
        load_agent_config(config_file)
