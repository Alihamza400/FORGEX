from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ToolConfig(BaseModel):
    name: str
    type: str = "builtin"
    config: dict[str, Any] = {}


class MemoryConfig(BaseModel):
    type: str = "none"
    collection: str = "default"
    embedding_model: str = "nomic-embed-text"
    top_k: int = 5
    score_threshold: float = 0.5


class ModelConfig(BaseModel):
    name: str = "llama3.2:3b"
    provider: str = "ollama"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9


class AgentConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    role: str = Field(..., min_length=1, max_length=1024)
    goal: str = Field(..., min_length=1, max_length=4096)
    model: ModelConfig = ModelConfig()
    tools: list[ToolConfig] = []
    memory: MemoryConfig = MemoryConfig()
    max_iterations: int = Field(default=10, ge=1, le=100)
    system_prompt_extra: str = ""
    environment: dict[str, str] = {}

    @model_validator(mode="after")
    def validate_tool_names(self) -> AgentConfig:
        names = [t.name for t in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("Tool names must be unique")
        return self


class AgentRunConfig(BaseModel):
    agent: AgentConfig
    task: str = Field(..., min_length=1, max_length=100000)
    stream: bool = False
    max_wait_seconds: int = 300


class TaskResult(BaseModel):
    agent_name: str
    task: str
    output: str
    iterations: int = 0
    tokens_used: int = 0
    error: str | None = None
    duration_ms: int = 0
