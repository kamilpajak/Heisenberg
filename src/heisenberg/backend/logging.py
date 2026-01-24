"""Structured logging configuration for Heisenberg backend."""

from __future__ import annotations

import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING, TextIO

import structlog

if TYPE_CHECKING:
    from structlog.typing import EventDict, WrappedLogger

# Context variable for request ID propagation across async calls
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def add_request_id(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add request_id to log event if set in context."""
    request_id = request_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    stream: TextIO | None = None,
) -> None:
    """
    Configure structured logging with structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, output JSON format; otherwise, console format.
        stream: Output stream (defaults to sys.stdout).
    """
    if stream is None:
        stream = sys.stdout

    # Common processors
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        add_request_id,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), log_level.upper(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,  # Disable caching for tests
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically module name).

    Returns:
        Configured structlog BoundLogger.
    """
    return structlog.get_logger(name).bind(logger=name)
