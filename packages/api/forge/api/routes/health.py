from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, Depends
from forge.auth.dependencies import get_optional_user
from forge.core.config import settings
from forge.core.logging import get_logger

logger = get_logger("forge.api.health")

router = APIRouter()


@dataclass
class ServiceHealth:
    name: str
    status: str = "unknown"
    latency_ms: int | None = None
    error: str | None = None


async def _check_ollama() -> ServiceHealth:
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        if resp.status_code == 200:
            return ServiceHealth(name="ollama", status="ok", latency_ms=latency)
        return ServiceHealth(name="ollama", status="error", latency_ms=latency, error=f"HTTP {resp.status_code}")
    except Exception as e:
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="ollama", status="error", latency_ms=latency, error=str(e))


async def _check_postgres() -> ServiceHealth:
    start = asyncio.get_event_loop().time()
    try:
        from forge.storage.postgres import Database

        db = Database()
        await db.connect()
        async with db.session() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        await db.close()
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="postgres", status="ok", latency_ms=latency)
    except Exception as e:
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="postgres", status="error", latency_ms=latency, error=str(e))


async def _check_redis() -> ServiceHealth:
    start = asyncio.get_event_loop().time()
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="redis", status="ok", latency_ms=latency)
    except Exception as e:
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="redis", status="error", latency_ms=latency, error=str(e))


async def _check_qdrant() -> ServiceHealth:
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.qdrant_url}/healthz")
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        if resp.status_code == 200:
            return ServiceHealth(name="qdrant", status="ok", latency_ms=latency)
        return ServiceHealth(name="qdrant", status="error", latency_ms=latency, error=f"HTTP {resp.status_code}")
    except Exception as e:
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="qdrant", status="error", latency_ms=latency, error=str(e))


async def _check_minio() -> ServiceHealth:
    start = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://{settings.minio_endpoint}/minio/health/live",
            )
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        if resp.status_code == 200:
            return ServiceHealth(name="minio", status="ok", latency_ms=latency)
        return ServiceHealth(name="minio", status="error", latency_ms=latency, error=f"HTTP {resp.status_code}")
    except Exception as e:
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return ServiceHealth(name="minio", status="error", latency_ms=latency, error=str(e))


@router.get("/health")
async def health_check(_=Depends(get_optional_user)):
    checks = await asyncio.gather(
        _check_ollama(),
        _check_postgres(),
        _check_redis(),
        _check_qdrant(),
        _check_minio(),
        return_exceptions=True,
    )

    services = {}
    overall = "ok"
    for c in checks:
        if isinstance(c, Exception):
            services["unknown"] = {"status": "error", "error": str(c)}
            overall = "degraded"
        else:
            svc = {"status": c.status}
            if c.latency_ms is not None:
                svc["latency_ms"] = c.latency_ms
            if c.error:
                svc["error"] = c.error
            services[c.name] = svc
            if c.status == "error":
                overall = "degraded"

    unhealthy = [k for k, v in services.items() if v.get("status") == "error"]
    if unhealthy:
        logger.warning("health check degraded", unhealthy=unhealthy)

    return {
        "status": overall,
        "version": "0.1.0",
        "services": services,
    }
