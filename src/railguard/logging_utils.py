"""Logging helpers shared across pipeline steps."""

import logging

_logger = logging.getLogger("railguard")


def log_rows(step: str, before: int, after: int) -> None:
    """Log the row count before and after a transformation step."""
    _logger.info("%s: rows before=%d after=%d", step, before, after)
