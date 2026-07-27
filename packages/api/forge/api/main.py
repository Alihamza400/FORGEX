from __future__ import annotations

import asyncio
import signal
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from forge.api.middleware import setup_security_middleware  # type: ignore[import-untyped]
from forge.api.routes import agents, auth, filesystem, health, logs, orchestrator, settings  # type: ignore[import-untyped]
from forge.core.config import settings
from forge.core.logging import configure_logging, get_logger
from forge.storage.postgres import Database as PgDatabase
from prometheus_client import REGISTRY, generate_latest
from starlette.responses import Response

logger = get_logger("forge.api")

_shutdown_event: asyncio.Event | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    global _shutdown_event
    configure_logging()

    _setup_tracing()
    await _setup_database()

    logger.info(
        "forge api starting",
        host=settings.api_host,
        port=settings.api_port,
        auth_enabled=bool(settings.api_secret_key),
        metrics_enabled=settings.metrics_enabled,
        tracing_enabled=settings.tracing_enabled,
    )
    if not settings.api_secret_key:
        logger.warning(
            "FORGE_API_SECRET_KEY not set — authentication is DISABLED. "
            "Set FORGE_API_SECRET_KEY in .env to enable auth."
        )

    _shutdown_event = asyncio.Event()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_shutdown(s)))  # type: ignore[misc]

    try:
        yield
    finally:
        logger.info("forge api shutting down gracefully")
        if _shutdown_event:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=30.0)
        logger.info("forge api shutdown complete")


async def _setup_database() -> None:
    try:
        db = PgDatabase()
        await db.connect()
        await db.create_all()
        await db.close()
        logger.info("database tables initialized")
    except Exception as e:
        logger.warning("database initialization failed", error=str(e))


def _setup_tracing() -> None:
    if not settings.tracing_enabled:
        logger.info("tracing disabled")
        return
    try:
        from forge.observability.tracing import setup_tracing

        setup_tracing(
            service_name=f"{settings.service_name}-api",
            otlp_endpoint=settings.otlp_endpoint,
            console_export=settings.otel_console_export,
        )
        logger.info("tracing initialized", endpoint=settings.otlp_endpoint)
    except Exception as e:
        logger.warning("failed to initialize tracing", error=str(e))


async def handle_shutdown(sig: signal.Signals) -> None:
    logger.info("received signal", signal=sig.name)
    if _shutdown_event:
        _shutdown_event.set()


app = FastAPI(
    title="Forge API",
    version="0.1.0",
    description="Self-hosted platform for building and deploying multi-agent AI systems",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Response:
    logger.info("request", method=request.method, path=request.url.path)
    response = await call_next(request)
    logger.info("response", status=response.status_code)
    return response  # type: ignore[no-any-return]


setup_security_middleware(app)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(filesystem.router, tags=["filesystem"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(orchestrator.router, tags=["orchestrator"])
app.include_router(logs.router, tags=["logs"])
app.include_router(settings.router, tags=["settings"])


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "Forge API",
        "version": "0.1.0",
        "auth_enabled": bool(settings.api_secret_key),
    }


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "alive"}


if settings.metrics_enabled:

    @app.get("/metrics")
    async def metrics_endpoint() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(REGISTRY), media_type="text/plain; version=0.0.4")


def main() -> None:
    uvicorn.run(
        "forge.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
