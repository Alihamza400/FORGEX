from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from forge.auth.dependencies import get_current_user, require_permission
from forge.core.agent_config import AgentConfig, TaskResult
from forge.core.config_loader import ConfigLoadError, load_agent_config
from forge.orchestrator.registry import get_registry
from forge.runtime.agent import AgentRuntime
from pydantic import BaseModel, Field

router = APIRouter()


class RunRequest(BaseModel):
    config_path: str = ""
    config: AgentConfig | None = None
    task: str = Field(..., min_length=1, max_length=100000)


class ValidateRequest(BaseModel):
    config_path: str
    config: AgentConfig | None = None


class ValidateResponse(BaseModel):
    valid: bool
    name: str = ""
    errors: list[str] = []


@router.get("/agents")
async def list_agents(_: Any = Depends(require_permission("agent:list"))) -> dict[str, Any]:
    registry = get_registry()
    return {"agents": [a.model_dump() for a in registry.list_agents()]}


@router.post("/agents/validate", response_model=ValidateResponse)
async def validate_agent(
    req: ValidateRequest,
    _: Any = Depends(require_permission("agent:create")),
) -> ValidateResponse:
    try:
        config = req.config or load_agent_config(req.config_path)
        return ValidateResponse(valid=True, name=config.name)
    except ConfigLoadError as e:
        return ValidateResponse(valid=False, errors=[str(e)])


@router.post("/agents/run", response_model=TaskResult)
async def run_agent(
    req: RunRequest,
    _: Any = Depends(get_current_user),
) -> TaskResult:
    try:
        if req.config:
            config = req.config
        elif req.config_path:
            config = load_agent_config(req.config_path)
        else:
            raise HTTPException(status_code=400, detail="Either config or config_path is required")
    except ConfigLoadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    runtime = AgentRuntime(config=config)
    try:
        await runtime.initialize()
        result = await runtime.run(req.task)
        return result
    finally:
        await runtime.close()
