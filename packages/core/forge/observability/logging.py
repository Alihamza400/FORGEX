from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog
from forge.core.config import settings
from opentelemetry import trace


def add_trace_context(
    _logger: structlog.stdlib.BoundLogger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = hex(span_context.trace_id)
        event_dict["span_id"] = hex(span_context.span_id)
    return event_dict


def add_correlation_id(
    _logger: structlog.stdlib.BoundLogger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    if "correlation_id" not in event_dict:
        event_dict["correlation_id"] = str(uuid.uuid4())[:8]
    return event_dict


def configure_observability_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_correlation_id,
        add_trace_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
