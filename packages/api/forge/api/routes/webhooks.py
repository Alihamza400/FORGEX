from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from forge.auth.dependencies import require_permission
from forge.core.logging import get_logger
from forge.storage.postgres import Database
from forge.storage.repository import WebhookRepository
from pydantic import BaseModel

logger = get_logger("forge.api.routes.webhooks")

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

EVENT_OPTIONS = [
    "agent.run.completed",
    "agent.run.failed",
]


class WebhookResponse(BaseModel):
    id: int
    name: str
    url: str
    events: list[str]
    secret: str | None
    active: int
    last_triggered_at: str | None
    last_response_code: int | None
    created_at: str
    updated_at: str


class CreateWebhookRequest(BaseModel):
    name: str
    url: str
    events: list[str] | None = None
    secret: str | None = None
    active: int = 1


class UpdateWebhookRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    active: int | None = None


class WebhookTestResult(BaseModel):
    success: bool
    status_code: int | None
    error: str | None = None


async def get_db() -> Database:
    db = Database()
    await db.connect()
    return db


def _model_to_response(hook: Any) -> WebhookResponse:
    return WebhookResponse(
        id=hook.id,
        name=hook.name,
        url=hook.url,
        events=hook.events or [],
        secret=hook.secret,
        active=hook.active,
        last_triggered_at=str(hook.last_triggered_at) if hook.last_triggered_at else None,
        last_response_code=hook.last_response_code,
        created_at=str(hook.created_at),
        updated_at=str(hook.updated_at),
    )


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    _: Any = Depends(require_permission("settings:read")),
) -> list[WebhookResponse]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = WebhookRepository(session)
            hooks = await repo.list_all()
            return [_model_to_response(h) for h in hooks]
    finally:
        await db.close()


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    req: CreateWebhookRequest,
    _: Any = Depends(require_permission("settings:update")),
) -> WebhookResponse:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = WebhookRepository(session)
            for h in await repo.list_all():
                if h.name == req.name:
                    raise HTTPException(status_code=409, detail=f"Webhook '{req.name}' already exists")
            hook = await repo.create(
                name=req.name,
                url=req.url,
                events=req.events,
                secret=req.secret,
                active=req.active,
            )
            return _model_to_response(hook)
    finally:
        await db.close()


@router.put("/{hook_id}", response_model=WebhookResponse)
async def update_webhook(
    hook_id: int,
    req: UpdateWebhookRequest,
    _: Any = Depends(require_permission("settings:update")),
) -> WebhookResponse:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = WebhookRepository(session)
            hook = await repo.get_by_id(hook_id)
            if not hook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
            if kwargs:
                hook = await repo.update(hook_id, **kwargs)
            if not hook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            return _model_to_response(hook)
    finally:
        await db.close()


@router.delete("/{hook_id}")
async def delete_webhook(
    hook_id: int,
    _: Any = Depends(require_permission("settings:update")),
) -> dict[str, Any]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = WebhookRepository(session)
            hook = await repo.get_by_id(hook_id)
            if not hook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            await repo.delete(hook_id)
            return {"status": "ok", "name": hook.name}
    finally:
        await db.close()


@router.post("/{hook_id}/test", response_model=WebhookTestResult)
async def test_webhook(
    hook_id: int,
    _: Any = Depends(require_permission("settings:read")),
) -> WebhookTestResult:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = WebhookRepository(session)
            hook = await repo.get_by_id(hook_id)
            if not hook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            payload = {
                "event": "webhook.test",
                "webhook_name": hook.name,
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {"message": "This is a test payload from Forge"},
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    headers = {"Content-Type": "application/json"}
                    if hook.secret:
                        headers["X-Webhook-Secret"] = hook.secret
                    res = await client.post(hook.url, json=payload, headers=headers)
                    return WebhookTestResult(success=res.is_success, status_code=res.status_code)
            except httpx.RequestError as e:
                return WebhookTestResult(success=False, status_code=None, error=str(e))
    finally:
        await db.close()
