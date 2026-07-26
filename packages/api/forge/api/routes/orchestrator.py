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
    OrchestrationConfig,
    OrchestrationResult,
    SubTaskResult,
    SubTaskStatus,
)
from forge.orchestrator.planner import TaskPlanner
from forge.orchestrator.registry import get_registry
from forge.storage.postgres import Database
from forge.storage.repository import TaskRepository, LogRepository
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


class MessageRequest(BaseModel):
    recipient: str
    type: str = "request"
    payload: dict[str, Any] = {}


class MessageResponse(BaseModel):
    message_id: str
    status: str


_orchestrations: dict[str, OrchestrationResult] = {}
_llm: OllamaClient | None = None


async def persist_result(result: OrchestrationResult) -> None:
    db = Database()
    try:
        await db.connect()
        async with db.session() as session:
            task_repo = TaskRepository(session)
            log_repo = LogRepository(session)
            for sr in result.sub_results:
                status = "completed" if sr.status == SubTaskStatus.COMPLETED else "failed"
                await task_repo.create(
                    agent_name=sr.agent_name or "orchestrator",
                    input=sr.description,
                    output=sr.output or sr.error,
                    status=status,
                    iterations=sr.iterations or 0,
                    tokens_used=sr.tokens or 0,
                )
            await log_repo.create(
                agent_name="orchestrator",
                level="INFO",
                message=f"Orchestration {result.id}: {result.status.value} - {result.final_output or result.error or ''}",
            )
            logger.info("persisted orchestration result", id=result.id, status=result.status.value)
    except Exception as e:
        logger.warning("failed to persist orchestration result", error=str(e))
    finally:
        await db.close()


from forge.core.logging import get_logger
logger = get_logger("forge.api.routes.orchestrator")


def _get_llm() -> OllamaClient:
    global _llm
    if _llm is None:
        _llm = OllamaClient(base_url=settings.ollama_base_url)
    return _llm


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(
    request: OrchestrateRequest,
    _: Any = Depends(require_permission("orchestrate:create")),
) -> OrchestrateResponse:
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
        await persist_result(result)

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
    _: Any = Depends(require_permission("orchestrate:read")),
) -> OrchestrateResponse:
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
    _: Any = Depends(require_permission("orchestrate:read")),
) -> list[SubTaskResult]:
    """Get the individual sub-task results for an orchestration."""
    result = _orchestrations.get(orchestration_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    return result.sub_results
