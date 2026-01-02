"""Structured logging for itch-creators scraper."""

import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = "itch-scraper",
    level: Optional[int] = None
) -> logging.Logger:
    """
    Configure structured logging for the scraper.

    Args:
        name: Logger name (usually __name__ from calling module)
        level: Logging level (defaults to INFO, or DEBUG if env var LOG_LEVEL=DEBUG)

    Returns:
        Configured logger instance

    Example:
        from .logger import setup_logger
        logger = setup_logger(__name__)
        logger.info("Processing started")
        logger.error("Something failed", exc_info=True)
    """
    import os

    # Determine log level from env or parameter
    if level is None:
        log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level_name, logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Console handler (outputs to stdout for Railway/Docker)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Format: [2025-01-01 12:30:45] [INFO] [module] Message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Don't propagate to root logger (avoid duplicate messages)
    logger.propagate = False

    return logger


class LogContext:
    """Context manager for adding context to log messages."""

    def __init__(self, logger: logging.Logger, context: str):
        self.logger = logger
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"{self.context} - Started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(f"{self.context} - Completed in {duration:.2f}s")
        else:
            self.logger.error(f"{self.context} - Failed after {duration:.2f}s: {exc_val}")

        return False  # Don't suppress exceptions


# Example usage functions
def log_with_stats(logger: logging.Logger, stats: dict, prefix: str = "Results"):
    """Log statistics dictionary in a readable format."""
    logger.info(f"{prefix}:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")


def log_error_with_context(logger: logging.Logger, operation: str, identifier: str, error: Exception):
    """Log an error with consistent formatting."""
    logger.error(f"✗ {operation} failed for '{identifier}': {type(error).__name__}: {error}")
