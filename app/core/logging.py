import logging
import sys
from typing import Any, Dict

import structlog


def configure_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    processors = [
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


def log_extra(request_id: str | None = None, correlation_id: str | None = None) -> Dict[str, Any]:
    extra: Dict[str, Any] = {}
    if request_id:
        extra["request_id"] = request_id
    if correlation_id:
        extra["correlation_id"] = correlation_id
    return extra
