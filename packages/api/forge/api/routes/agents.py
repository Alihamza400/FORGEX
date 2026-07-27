from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from forge.auth.dependencies import get_current_user, require_permission
from forge.core.agent_config import AgentConfig, TaskResult
from forge.core.config_loader import ConfigLoadError, load_agent_config
from forge.orchestrator.registry import get_registry
from forge.runtime.agent import AgentRuntime
from forge.storage.postgres import Database
from forge.storage.repository import AgentRepository
from pydantic import BaseModel, Field

router = APIRouter()


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    role: str = Field(..., min_length=1, max_length=1024)
    goal: str = Field(..., min_length=1, max_length=4096)
    config_yaml: str = ""
    model_name: str = "llama3.2:3b"


class AgentUpdateRequest(BaseModel):
    role: str | None = None
    goal: str | None = None
    config_yaml: str | None = None
    model_name: str | None = None
    status: str | None = None


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    goal: str
    model_name: str
    status: str
    created_at: str
    updated_at: str


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


async def get_db() -> Database:
    db = Database()
    await db.connect()
    return db


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(_: Any = Depends(require_permission("agent:list"))) -> list[AgentResponse]:
    registry = get_registry()
    return [{"id": 0, "name": a.name, "role": a.name, "goal": "", "model_name": "", "status": "", "created_at": "", "updated_at": ""} for a in registry.list_agents()]


@router.post("/agents", response_model=dict[str, Any], status_code=201)
async def create_agent(
    req: AgentCreateRequest,
    _: Any = Depends(require_permission("agent:create")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentRepository(session)
            agent = await repo.create(
                name=req.name,
                role=req.role,
                goal=req.goal,
                config_yaml=req.config_yaml or None,
                model_name=req.model_name,
            )
            return {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "goal": agent.goal,
                "model_name": agent.model_name,
                "status": agent.status,
                "created_at": str(agent.created_at),
                "updated_at": str(agent.updated_at),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        await db.close()


@router.get("/agents/{name}", response_model=dict[str, Any])
async def get_agent(
    name: str,
    _: Any = Depends(require_permission("agent:read")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentRepository(session)
            agent = await repo.get_by_name(name)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            return {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "goal": agent.goal,
                "config_yaml": agent.config_yaml or "",
                "model_name": agent.model_name,
                "status": agent.status,
                "created_at": str(agent.created_at),
                "updated_at": str(agent.updated_at),
            }
    finally:
        await db.close()


@router.put("/agents/{name}", response_model=dict[str, Any])
async def update_agent(
    name: str,
    req: AgentUpdateRequest,
    _: Any = Depends(require_permission("agent:update")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentRepository(session)
            agent = await repo.get_by_name(name)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
            if kwargs:
                agent = await repo.update(agent.id, **kwargs)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            return {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "goal": agent.goal,
                "model_name": agent.model_name,
                "status": agent.status,
                "updated_at": str(agent.updated_at),
            }
    finally:
        await db.close()


@router.delete("/agents/{name}", response_model=dict[str, Any])
async def delete_agent(
    name: str,
    _: Any = Depends(require_permission("agent:delete")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentRepository(session)
            agent = await repo.get_by_name(name)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            await repo.delete(agent.id)
            return {"message": f"Agent '{name}' deleted", "name": name}
    finally:
        await db.close()


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


@router.post("/agents/run/stream")
async def run_agent_stream(
    req: RunRequest,
    _: Any = Depends(get_current_user),
) -> StreamingResponse:
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
    await runtime.initialize()

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in runtime.run_streaming(req.task):
                yield event
        finally:
            await runtime.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
