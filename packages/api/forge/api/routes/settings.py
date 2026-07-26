from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from forge.auth.dependencies import require_permission
from forge.core.config import settings
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    api_host: str
    api_port: int
    auth_enabled: bool
    log_level: str
    log_json: bool
    ollama_base_url: str
    default_model: str
    qdrant_url: str
    redis_url: str
    minio_endpoint: str
    data_dir: str
    token_expire_minutes: int
    rate_limit_per_minute: int
    metrics_enabled: bool
    tracing_enabled: bool
    otlp_endpoint: str | None


class SettingsUpdateRequest(BaseModel):
    log_level: str | None = None
    log_json: bool | None = None
    default_model: str | None = None
    token_expire_minutes: int | None = None
    rate_limit_per_minute: int | None = None
    metrics_enabled: bool | None = None
    tracing_enabled: bool | None = None
    otlp_endpoint: str | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings(
    _: Any = Depends(require_permission("settings:read")),
) -> SettingsResponse:
    return SettingsResponse(
        api_host=settings.api_host,
        api_port=settings.api_port,
        auth_enabled=bool(settings.api_secret_key),
        log_level=settings.log_level,
        log_json=settings.log_json,
        ollama_base_url=settings.ollama_base_url,
        default_model=settings.ollama_default_model,
        qdrant_url=settings.qdrant_url,
        redis_url=settings.redis_url,
        minio_endpoint=settings.minio_endpoint,
        data_dir=str(settings.data_dir),
        token_expire_minutes=settings.token_expire_minutes,
        rate_limit_per_minute=settings.rate_limit_per_minute,
        metrics_enabled=settings.metrics_enabled,
        tracing_enabled=settings.tracing_enabled,
        otlp_endpoint=settings.otlp_endpoint,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    _: Any = Depends(require_permission("settings:update")),
) -> SettingsResponse:
    updates = req.model_dump(exclude_none=True)
    if updates:
        logger.info("settings updated (not persisted)", updates=updates)
    return await get_settings(_)


from forge.core.logging import get_logger
logger = get_logger("forge.api.routes.settings")
