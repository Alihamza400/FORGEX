from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class AgentCapability(StrEnum):
    SEARCH = "search"
    ANALYSIS = "analysis"
    CODE = "code"
    WRITING = "writing"
    REASONING = "reasoning"
    SUMMARIZATION = "summarization"
    CUSTOM = "custom"


class OrchestrationStrategy(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    SUPERVISOR = "supervisor"
    AUTO = "auto"


class SubTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionMode(StrEnum):
    SYNC = "sync"
    ASYNC = "async"


class FallbackBehavior(StrEnum):
    ERROR = "error"
    RETRY = "retry"
    SKIP = "skip"
    DELEGATE = "delegate"


class AgentDescriptor(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    role: str = Field(..., min_length=1, max_length=1024)
    goal: str = Field(default="", max_length=4096)
    capabilities: list[AgentCapability] = []
    status: AgentStatus = AgentStatus.IDLE
    last_heartbeat: datetime | None = None
    endpoint: str | None = None
    metadata: dict[str, Any] = {}


class SubTaskDef(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    description: str
    agent_role: str = ""
    agent_capabilities: list[AgentCapability] = []
    depends_on: list[str] = []
    context: str = ""
    max_iterations: int = Field(default=10, ge=1, le=100)
    priority: int = Field(default=0, ge=0, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class SubTaskResult(BaseModel):
    sub_task_id: str
    description: str
    status: SubTaskStatus
    agent_name: str = ""
    output: str = ""
    error: str | None = None
    iterations: int = 0
    tokens_used: int = 0
    duration_ms: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class OrchestrationConfig(BaseModel):
    strategy: OrchestrationStrategy = OrchestrationStrategy.AUTO
    agent_roles: list[str] = Field(default_factory=list, min_length=1)
    max_concurrency: int = Field(default=3, ge=1, le=50)
    timeout_seconds: int = Field(default=600, ge=1, le=86400)
    max_iterations_per_agent: int = Field(default=10, ge=1, le=100)
    token_budget: int = Field(default=100_000, ge=100, le=10_000_000)
    fallback_behavior: FallbackBehavior = FallbackBehavior.ERROR
    enable_task_planning: bool = True
    enable_supervisor: bool = False
    enable_parallel: bool = True
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    context: dict[str, Any] = {}


class OrchestrationResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    task: str
    strategy: OrchestrationStrategy
    status: SubTaskStatus
    sub_results: list[SubTaskResult] = []
    final_output: str = ""
    total_iterations: int = 0
    total_tokens: int = 0
    total_duration_ms: int = 0
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    type: str = "request"
    sender: str
    recipient: str = ""
    sub_task_id: str = ""
    payload: dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = Field(default=60, ge=1, le=3600)
    correlation_id: str = ""
