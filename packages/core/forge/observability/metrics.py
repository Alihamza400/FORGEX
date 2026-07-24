from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    labelnames=["method"],
)

agent_tasks_total = Counter(
    "agent_tasks_total",
    "Total agent tasks executed",
    labelnames=["status"],
)

agent_tasks_duration_seconds = Histogram(
    "agent_tasks_duration_seconds",
    "Agent task duration in seconds",
    labelnames=[],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM inference requests",
    labelnames=["model", "status"],
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    labelnames=["model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens processed",
    labelnames=["model", "type"],
)

memory_operations_total = Counter(
    "memory_operations_total",
    "Total memory operations",
    labelnames=["operation", "status"],
)

orchestrator_tasks_total = Counter(
    "orchestrator_tasks_total",
    "Total orchestrator tasks",
    labelnames=["pattern", "status"],
)

active_connections = Gauge(
    "active_connections",
    "Active connections by type",
    labelnames=["type"],
)

db_pool_size = Gauge(
    "db_pool_size",
    "Database connection pool size",
    labelnames=["pool"],
)


class MetricsManager:
    def observe_http_request(
        self, method: str, path: str, status: int, duration: float
    ) -> None:
        http_requests_total.labels(method=method, path=path, status=str(status)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

    @staticmethod
    def track_agent_task(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                agent_tasks_total.labels(status="success").inc()
                return result
            except Exception:
                agent_tasks_total.labels(status="error").inc()
                raise
            finally:
                agent_tasks_duration_seconds.observe(time.time() - start)

        return wrapper

    @staticmethod
    def track_llm_request(model: str) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    llm_requests_total.labels(model=model, status="success").inc()
                    return result
                except Exception:
                    llm_requests_total.labels(model=model, status="error").inc()
                    raise
                finally:
                    llm_request_duration_seconds.labels(model=model).observe(
                        time.time() - start
                    )

            return wrapper

        return decorator

    @staticmethod
    def record_tokens(model: str, token_type: str, count: int) -> None:
        llm_tokens_total.labels(model=model, type=token_type).inc(count)

    @staticmethod
    def record_memory_op(operation: str, status: str) -> None:
        memory_operations_total.labels(operation=operation, status=status).inc()

    @staticmethod
    def record_orchestrator_task(pattern: str, status: str) -> None:
        orchestrator_tasks_total.labels(pattern=pattern, status=status).inc()


metrics = MetricsManager()
