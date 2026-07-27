from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from forge.auth.dependencies import require_permission
from forge.core.agent_config import AgentConfig
from forge.core.logging import get_logger
from forge.storage.postgres import Database
from forge.storage.repository import AgentTemplateRepository
from pydantic import BaseModel

logger = get_logger("forge.api.routes.templates")

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: str | None
    config_json: dict[str, Any]
    category: str | None
    tags: list[str] | None
    usage_count: int
    created_at: str
    updated_at: str


class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    config_json: dict[str, Any]
    category: str | None = None
    tags: list[str] | None = None


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    config_json: dict[str, Any] | None = None
    category: str | None = None
    tags: list[str] | None = None


async def get_db() -> Database:
    db = Database()
    await db.connect()
    return db


def _model_to_response(tmpl: Any) -> TemplateResponse:
    return TemplateResponse(
        id=tmpl.id,
        name=tmpl.name,
        description=tmpl.description,
        config_json=tmpl.config_json,
        category=tmpl.category,
        tags=tmpl.tags,
        usage_count=tmpl.usage_count,
        created_at=str(tmpl.created_at),
        updated_at=str(tmpl.updated_at),
    )


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = Query(default=None),
    _: Any = Depends(require_permission("agent:list")),
) -> list[TemplateResponse]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentTemplateRepository(session)
            templates = await repo.list_all(category=category)
            return [_model_to_response(t) for t in templates]
    finally:
        await db.close()


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    req: CreateTemplateRequest,
    _: Any = Depends(require_permission("agent:create")),
) -> TemplateResponse:
    try:
        AgentConfig.model_validate(req.config_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid agent config: {e}") from e

    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentTemplateRepository(session)
            tmpl = await repo.create(
                name=req.name,
                description=req.description,
                config_json=req.config_json,
                category=req.category,
                tags=req.tags,
            )
            return _model_to_response(tmpl)
    finally:
        await db.close()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    _: Any = Depends(require_permission("agent:read")),
) -> TemplateResponse:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentTemplateRepository(session)
            tmpl = await repo.get_by_id(template_id)
            if not tmpl:
                raise HTTPException(status_code=404, detail="Template not found")
            return _model_to_response(tmpl)
    finally:
        await db.close()


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    req: UpdateTemplateRequest,
    _: Any = Depends(require_permission("agent:update")),
) -> TemplateResponse:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentTemplateRepository(session)
            tmpl = await repo.get_by_id(template_id)
            if not tmpl:
                raise HTTPException(status_code=404, detail="Template not found")
            if req.config_json:
                try:
                    AgentConfig.model_validate(req.config_json)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Invalid agent config: {e}") from e
            kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
            if kwargs:
                tmpl = await repo.update(template_id, **kwargs)
            if not tmpl:
                raise HTTPException(status_code=404, detail="Template not found")
            return _model_to_response(tmpl)
    finally:
        await db.close()


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    _: Any = Depends(require_permission("agent:delete")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentTemplateRepository(session)
            tmpl = await repo.get_by_id(template_id)
            if not tmpl:
                raise HTTPException(status_code=404, detail="Template not found")
            await repo.delete(template_id)
            return {"status": "ok", "name": tmpl.name}
    finally:
        await db.close()


@router.post("/{template_id}/use")
async def use_template(
    template_id: int,
    _: Any = Depends(require_permission("agent:create")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = AgentTemplateRepository(session)
            tmpl = await repo.get_by_id(template_id)
            if not tmpl:
                raise HTTPException(status_code=404, detail="Template not found")
            await repo.increment_usage(template_id)
            return {"status": "ok", "name": tmpl.name, "config": tmpl.config_json}
    finally:
        await db.close()
