from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from forge.auth.dependencies import require_permission
from forge.core.agent_config import AgentConfig
from forge.core.config import settings
from forge.llm.client import OllamaClient
from forge.orchestrator.coordinator import OrchestratorCoordinator
from forge.orchestrator.exceptions import OrchestratorError
from forge.orchestrator.models import (
    AgentDescriptor,
    OrchestrationConfig,
    OrchestrationResult,
    SubTaskResult,
)
from forge.orchestrator.planner import TaskPlanner
from forge.orchestrator.registry import get_registry
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["orchestrator"])


class OrchestrateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=100000)
    agents: dict[str, AgentConfig]
    config: OrchestrationConfig = OrchestrationConfig()


class OrchestrateResponse(BaseModel):
    id: str
    status: str
    result: OrchestrationResult | None = None
    error: str | None = None


class AgentListResponse(BaseModel):
    agents: list[AgentDescriptor]


class MessageRequest(BaseModel):
    recipient: str
    type: str = "request"
    payload: dict[str, Any] = {}


class MessageResponse(BaseModel):
    message_id: str
    status: str


_orchestrations: dict[str, OrchestrationResult] = {}
_llm: OllamaClient | None = None


def _get_llm() -> OllamaClient:
    global _llm
    if _llm is None:
        _llm = OllamaClient(base_url=settings.ollama_base_url)
    return _llm


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(_=Depends(require_permission("agent:list"))):
    """List all registered agents with their capabilities and status."""
    registry = get_registry()
    return AgentListResponse(agents=registry.list())


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(
    request: OrchestrateRequest,
    _=Depends(require_permission("orchestrate:create")),
):
    """Execute a multi-agent orchestration."""
    llm = _get_llm()
    registry = get_registry()

    for name, cfg in request.agents.items():
        registry.register(
            name=name,
            role=cfg.role,
            goal=cfg.goal,
            endpoint=None,
        )

    planner = TaskPlanner(llm_client=llm, registry=registry)
    coordinator = OrchestratorCoordinator(
        llm_client=llm,
        registry=registry,
        planner=planner,
        agents=request.agents,
    )

    try:
        result = await coordinator.orchestrate(request.task, request.config)
        _orchestrations[result.id] = result

        return OrchestrateResponse(
            id=result.id,
            status=result.status.value,
            result=result,
        )
    except OrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/orchestrate/{orchestration_id}", response_model=OrchestrateResponse)
async def get_orchestration(
    orchestration_id: str,
    _=Depends(require_permission("orchestrate:read")),
):
    """Get the status and result of an orchestration."""
    result = _orchestrations.get(orchestration_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    return OrchestrateResponse(
        id=result.id,
        status=result.status.value,
        result=result,
    )


@router.get("/orchestrate/{orchestration_id}/sub-tasks", response_model=list[SubTaskResult])
async def get_orchestration_sub_tasks(
    orchestration_id: str,
    _=Depends(require_permission("orchestrate:read")),
):
    """Get the individual sub-task results for an orchestration."""
    result = _orchestrations.get(orchestration_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    return result.sub_results
