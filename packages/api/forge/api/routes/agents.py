from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from forge.core.logging import get_logger

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from forge.auth.dependencies import get_current_user, require_permission
from forge.core.agent_config import AgentConfig, TaskResult
from forge.core.config_loader import ConfigLoadError, load_agent_config
from forge.runtime.agent import AgentRuntime
from forge.storage.postgres import Database
from forge.storage.repository import AgentRepository, TaskRepository
from pydantic import BaseModel, Field

logger = get_logger("forge.api.routes.agents")

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


class RunHistoryResponse(BaseModel):
    id: int
    agent_name: str
    input: str
    output: str | None
    status: str
    error: str | None
    iterations: int
    tokens_used: int
    duration_ms: int
    created_at: str
    finished_at: str | None


class ValidateRequest(BaseModel):
    config_path: str = ""
    config: AgentConfig | None = None


class ValidateResponse(BaseModel):
    valid: bool
    name: str = ""
    errors: list[str] = []


async def _persist_task(agent_name: str, task: str, result: TaskResult) -> None:
    db = Database()
    try:
        await db.connect()
        async with db.session() as session:
            repo = TaskRepository(session)
            status = "completed" if not result.error else "failed"
            await repo.create(
                agent_name=agent_name,
                input=task,
                output=result.output,
                status=status,
                error=result.error,
                iterations=result.iterations,
                tokens_used=result.tokens_used,
                duration_ms=result.duration_ms,
                finished_at=datetime.now(),
            )
    except Exception as e:
        logger.warning("failed to persist task result", error=str(e))
    finally:
        await db.close()

    event = f"agent.run.{status}"
    asyncio.ensure_future(
        _dispatch_webhooks(agent_name, event, {
            "task": task,
            "output": result.output,
            "status": status,
            "error": result.error,
            "iterations": result.iterations,
            "tokens_used": result.tokens_used,
            "duration_ms": result.duration_ms,
        }),
    )


async def _dispatch_webhooks(
    agent_name: str,
    event: str,
    payload: dict[str, Any],
) -> None:
    db = Database()
    try:
        await db.connect()
        async with db.session() as session:
            from forge.storage.repository import WebhookRepository
            repo = WebhookRepository(session)
            hooks = await repo.get_active_by_event(event)
            if not hooks:
                return
            for hook in hooks:
                body = {"event": event, "agent_name": agent_name, "data": payload, "timestamp": datetime.now().isoformat()}
                try:
                    headers = {"Content-Type": "application/json"}
                    if hook.secret:
                        headers["X-Webhook-Secret"] = hook.secret
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.post(hook.url, json=body, headers=headers)
                    await repo.update(
                        hook.id,
                        last_triggered_at=datetime.now(),
                        last_response_code=res.status_code,
                    )
                except Exception as e:
                    logger.warning("webhook dispatch failed", hook=hook.name, error=str(e))
                    await repo.update(
                        hook.id,
                        last_triggered_at=datetime.now(),
                        last_response_code=None,
                    )
    except Exception as e:
        logger.warning("webhook dispatch error", error=str(e))
    finally:
        await db.close()


async def get_db() -> Database:
    db = Database()
    await db.connect()
    return db


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    _: Any = Depends(require_permission("agent:list")),
) -> list[AgentResponse]:
    db = Database()
    try:
        await db.connect()
        async with db.session() as session:
            repo = AgentRepository(session)
            agents = await repo.list_all()
            agents = agents[offset:offset + limit]
            return [
                AgentResponse(
                    id=a.id,
                    name=a.name,
                    role=a.role,
                    goal=a.goal,
                    model_name=a.model_name or "",
                    status=a.status,
                    created_at=str(a.created_at),
                    updated_at=str(a.updated_at),
                )
                for a in agents
            ]
    finally:
        await db.close()


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
        await _persist_task(config.name, req.task, result)
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
        last_result: TaskResult | None = None
        try:
            async for event in runtime.run_streaming(req.task):
                if isinstance(event, str) and '"type":"done"' in event:
                    try:
                        parsed = json.loads(event[6:]) if event.startswith("data: ") else json.loads(event)
                        if parsed.get("type") == "done":
                            last_result = TaskResult(**parsed["data"])
                    except Exception:
                        pass
                yield event
        finally:
            await runtime.close()
            if last_result:
                await _persist_task(config.name, req.task, last_result)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agents/{name}/runs", response_model=list[RunHistoryResponse])
async def list_agent_runs(
    name: str,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    _: Any = Depends(require_permission("agent:read")),
) -> list[RunHistoryResponse]:
    db = Database()
    try:
        await db.connect()
        async with db.session() as session:
            repo = TaskRepository(session)
            tasks = await repo.list_by_agent(agent_name=name, limit=limit, offset=offset)
            return [
                RunHistoryResponse(
                    id=t.id,
                    agent_name=t.agent_name,
                    input=t.input,
                    output=t.output,
                    status=t.status,
                    error=t.error,
                    iterations=t.iterations,
                    tokens_used=t.tokens_used,
                    duration_ms=t.duration_ms,
                    created_at=str(t.created_at),
                    finished_at=str(t.finished_at) if t.finished_at else None,
                )
                for t in tasks
            ]
    finally:
        await db.close()


@router.get("/agents/{name}/runs/{task_id}", response_model=RunHistoryResponse)
async def get_agent_run(
    name: str,
    task_id: int,
    _: Any = Depends(require_permission("agent:read")),
) -> RunHistoryResponse:
    db = Database()
    try:
        await db.connect()
        async with db.session() as session:
            repo = TaskRepository(session)
            task = await repo.get_by_id(task_id)
            if not task or task.agent_name != name:
                raise HTTPException(status_code=404, detail="Run not found")
            return RunHistoryResponse(
                id=task.id,
                agent_name=task.agent_name,
                input=task.input,
                output=task.output,
                status=task.status,
                error=task.error,
                iterations=task.iterations,
                tokens_used=task.tokens_used,
                duration_ms=task.duration_ms,
                created_at=str(task.created_at),
                finished_at=str(task.finished_at) if task.finished_at else None,
            )
    finally:
        await db.close()
