from __future__ import annotations

import pytest
from forge.core.agent_config import AgentConfig, MemoryConfig, ModelConfig, ToolConfig
from pydantic import ValidationError


class TestAgentConfig:
    def test_minimal_valid_config(self):
        config = AgentConfig(name="test-agent", role="helper", goal="help users")
        assert config.name == "test-agent"
        assert config.role == "helper"
        assert config.goal == "help users"
        assert isinstance(config.model, ModelConfig)
        assert config.tools == []
        assert isinstance(config.memory, MemoryConfig)
    def test_default_values(self):
        config = AgentConfig(name="a", role="r", goal="g")
        assert config.model.name == "llama3.2:3b"
        assert config.model.provider == "ollama"
        assert config.model.temperature == 0.7
        assert config.max_iterations == 10
        assert config.memory.type == "none"
    def test_invalid_empty_name(self):
        with pytest.raises(ValidationError):
            AgentConfig(name="", role="r", goal="g")
    def test_duplicate_tool_names_raises(self):
        with pytest.raises(ValidationError, match="must be unique"):
            AgentConfig(
                name="a",
                role="r",
                goal="g",
                tools=[
                    ToolConfig(name="web_search"),
                    ToolConfig(name="web_search"),
                ],
            )
    def test_custom_model_config(self):
        config = AgentConfig(
            name="a",
            role="r",
            goal="g",
            model=ModelConfig(name="mixtral:8x7b", temperature=0.1, max_tokens=8192),
        )
        assert config.model.name == "mixtral:8x7b"
        assert config.model.temperature == 0.1
        assert config.model.max_tokens == 8192
    def test_tools_with_config(self):
        config = AgentConfig(
            name="a",
            role="r",
            goal="g",
            tools=[
                ToolConfig(name="filesystem", type="mcp", config={"allowed_dirs": ["/data"]}),
            ],
        )
        assert config.tools[0].type == "mcp"
        assert config.tools[0].config["allowed_dirs"] == ["/data"]
    def test_memory_config(self):
        config = AgentConfig(
            name="a",
            role="r",
            goal="g",
            memory=MemoryConfig(type="qdrant", top_k=10, score_threshold=0.7),
        )
        assert config.memory.type == "qdrant"
        assert config.memory.top_k == 10
        assert config.memory.score_threshold == 0.7
