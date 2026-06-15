"""Structured logging configuration."""

import logging
import sys

from backend.core.config import settings


def configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)

    # Mute noisy third-party loggers
    noisy_loggers = [
        "httpcore",
        "httpx",
        "urllib3",
        "openai",
        "qdrant_client",
        "hpack",
        "asyncio",
        "huggingface_hub",
        "filelock",
        "sqlfluff",
        "sqlfluff.lexer",
        "sqlfluff.parser",
        "sqlfluff.linter",
        "sqlfluff.config",
        "sqlfluff.plugin",
        "sqlfluff.templater",
        "sqlfluff.rules",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

