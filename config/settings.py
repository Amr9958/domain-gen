"""Centralized application settings with optional .env loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency during bootstrap
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")


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


@dataclass(frozen=True)
class AppSettings:
    """Shared runtime settings for local and cloud-enabled execution."""

    app_title: str = os.getenv("APP_TITLE", "DomainTrade Pro V5")
    app_icon: str = os.getenv("APP_ICON", "🔥")
    app_layout: str = os.getenv("APP_LAYOUT", "wide")

    data_dir: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
    local_db_path: Path = Path(os.getenv("LOCAL_DB_PATH", str(BASE_DIR / "domains.db")))
    word_banks_dir: Path = Path(os.getenv("WORD_BANKS_DIR", str(BASE_DIR / "word_banks")))

    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir: Path = Path(os.getenv("LOG_DIR", str(BASE_DIR / ".logs")))
    log_file_name: str = os.getenv("LOG_FILE_NAME", "app.log")

    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_key: str = os.getenv("SUPABASE_KEY", "").strip()
    supabase_timeout_seconds: int = _get_int("SUPABASE_TIMEOUT_SECONDS", 15)
    use_supabase: bool = _get_bool("USE_SUPABASE", False)

    default_ai_provider: str = os.getenv("DEFAULT_AI_PROVIDER", "xAI (Grok)")

    @property
    def log_file_path(self) -> Path:
        """Return the fully qualified application log path."""
        return self.log_dir / self.log_file_name

    @property
    def supabase_enabled(self) -> bool:
        """Return True when cloud storage is explicitly enabled and configured."""
        return self.use_supabase and bool(self.supabase_url and self.supabase_key)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Build cached application settings once per process."""
    settings = AppSettings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
