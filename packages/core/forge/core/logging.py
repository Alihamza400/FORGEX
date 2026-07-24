from __future__ import annotations

import logging
import sys

import structlog
from forge.core.config import settings
from forge.observability.logging import configure_observability_logging


def configure_logging() -> None:
    configure_observability_logging()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name or __name__)
