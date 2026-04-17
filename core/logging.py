"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

from config import get_settings


def configure_logging(log_file_path: Path | None = None) -> logging.Logger:
    """Configure the root logger once and return an app-scoped logger."""
    settings = get_settings()
    target_path = log_file_path or settings.log_file_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(target_path, encoding="utf-8"),
            ],
        )
    else:
        root_logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

    logger = logging.getLogger("trend_domain")
    logger.debug("Logging configured at %s", settings.log_level)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""
    configure_logging()
    return logging.getLogger(f"trend_domain.{name}")
