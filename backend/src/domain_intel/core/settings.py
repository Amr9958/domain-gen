"""Environment-backed backend settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during early bootstrap
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = PROJECT_ROOT / "backend"

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(BACKEND_DIR / ".env", override=True)


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_csv(name: str, default: str = "") -> List[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass(frozen=True)
class BackendSettings:
    """Typed settings used by the FastAPI backend and database layer."""

    app_name: str = os.getenv("DOMAIN_INTEL_APP_NAME", "Domain Intelligence API")
    environment: str = os.getenv("DOMAIN_INTEL_ENV", "local")
    debug: bool = _get_bool("DOMAIN_INTEL_DEBUG", False)
    api_v1_prefix: str = os.getenv("DOMAIN_INTEL_API_V1_PREFIX", "/v1")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://domain_intel:domain_intel@localhost:5432/domain_intel",
    )
    database_pool_size: int = _get_int("DATABASE_POOL_SIZE", 5)
    database_max_overflow: int = _get_int("DATABASE_MAX_OVERFLOW", 10)
    database_echo: bool = _get_bool("DATABASE_ECHO", False)

    cors_allowed_origins: Optional[List[str]] = None
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def __post_init__(self) -> None:
        if self.cors_allowed_origins is None:
            object.__setattr__(
                self,
                "cors_allowed_origins",
                _get_csv("CORS_ALLOWED_ORIGINS", "http://localhost:3000"),
            )


@lru_cache(maxsize=1)
def get_settings() -> BackendSettings:
    """Return cached backend settings for dependency injection."""

    return BackendSettings()
