from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from forge.core.config import settings
from forge.core.logging import get_logger
from forge.observability.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)
from starlette.middleware.base import BaseHTTPMiddleware

logger = get_logger("forge.api.middleware")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, max_requests: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if path.startswith("/api/v1/auth") or path == "/api/v1/health":
            return await call_next(request)

        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            bucket_key = f"{client_ip}:{path}"

            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = []

            self._buckets[bucket_key] = [
                t for t in self._buckets[bucket_key] if t > window_start
            ]

            if len(self._buckets[bucket_key]) >= self.max_requests:
                logger.warning("rate limit exceeded", ip=client_ip, path=path)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Try again later.",
                        "retry_after_seconds": int(self._buckets[bucket_key][0] + self.window_seconds - now),
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(int(self._buckets[bucket_key][0] + self.window_seconds - now)),
                    },
                )

            self._buckets[bucket_key].append(now)

        response = await call_next(request)
        async with self._lock:
            remaining = max(0, self.max_requests - len(self._buckets.get(bucket_key, [])))
            response.headers["X-RateLimit-Limit"] = str(self.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"

        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        method = request.method
        path = _get_route_path(request)

        if path.startswith("/metrics") or path.startswith("/livez") or path.startswith("/readyz"):
            return await call_next(request)

        http_requests_in_progress.labels(method=method).inc()
        start = time.time()

        try:
            response = await call_next(request)
            status = response.status_code
            http_requests_total.labels(method=method, path=path, status=str(status)).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(
                time.time() - start
            )
            return response
        except Exception:
            http_requests_total.labels(method=method, path=path, status="500").inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(
                time.time() - start
            )
            raise
        finally:
            http_requests_in_progress.labels(method=method).dec()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.time()

        response = await call_next(request)

        duration_ms = int((time.time() - start) * 1000)
        logger.info("audit",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            ip=request.client.host if request.client else None,
            ua=request.headers.get("user-agent"),
        )

        return response


def _get_route_path(request: Request) -> str:
    return request.url.path


def setup_security_middleware(app: FastAPI) -> None:
    rate_limit = settings.rate_limit_per_minute
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit, window_seconds=60)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditMiddleware)
    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware)
