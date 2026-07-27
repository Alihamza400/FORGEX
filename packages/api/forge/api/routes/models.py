from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from forge.auth.dependencies import require_permission
from forge.llm.client import OllamaClient
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/models", tags=["models"])


class ModelInfo(BaseModel):
    name: str
    size: int
    modified: str
    digest: str


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str


class PullModelRequest(BaseModel):
    name: str


@router.get("", response_model=ModelListResponse)
async def list_models(
    _: Any = Depends(require_permission("settings:read")),
) -> ModelListResponse:
    from forge.core.config import settings

    client = OllamaClient()
    try:
        raw = await client.list_models()
        models = [
            ModelInfo(
                name=m.get("name", ""),
                size=m.get("size", 0),
                modified_at=m.get("modified_at", ""),
                digest=m.get("digest", ""),
            )
            for m in raw
        ]
        return ModelListResponse(
            models=models,
            default_model=settings.ollama_default_model,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {e}")


@router.post("/pull", response_model=dict[str, Any])
async def pull_model(
    req: PullModelRequest,
    _: Any = Depends(require_permission("settings:update")),
) -> dict[str, Any]:
    client = OllamaClient()
    try:
        result = await client.pull_model(req.name)
        return {"status": "success", "model": req.name, "details": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
