"""Optional Supabase integration layer for cloud-backed storage."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from config import get_settings
from core.logging import get_logger

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - optional dependency during bootstrap
    Client = Any  # type: ignore[assignment]
    create_client = None


logger = get_logger("supabase")


@dataclass(frozen=True)
class SupabaseHealth:
    """Human-readable Supabase availability snapshot."""

    enabled: bool
    configured: bool
    client_ready: bool
    reason: str = ""


class SupabaseClientManager:
    """Lazy manager for the optional Supabase client."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Client | None = None

    def health(self) -> SupabaseHealth:
        """Return current configuration and client readiness status."""
        if not self.settings.use_supabase:
            return SupabaseHealth(
                enabled=False,
                configured=bool(self.settings.supabase_url and self.settings.supabase_key),
                client_ready=False,
                reason="Supabase is disabled; local SQLite remains active.",
            )
        if not self.settings.supabase_enabled:
            return SupabaseHealth(
                enabled=True,
                configured=False,
                client_ready=False,
                reason="SUPABASE_URL or SUPABASE_KEY is missing.",
            )
        if create_client is None:
            return SupabaseHealth(
                enabled=True,
                configured=True,
                client_ready=False,
                reason="The supabase package is not installed.",
            )
        return SupabaseHealth(
            enabled=True,
            configured=True,
            client_ready=True,
            reason="Supabase client is ready.",
        )

    def get_client(self) -> Client | None:
        """Create and cache the Supabase client when configuration allows it."""
        health = self.health()
        if not health.client_ready:
            logger.info("Supabase client unavailable: %s", health.reason)
            return None

        if self._client is None:
            assert create_client is not None
            self._client = create_client(self.settings.supabase_url, self.settings.supabase_key)
            logger.info("Supabase client initialized.")
        return self._client

    def table(self, table_name: str) -> Any | None:
        """Return a table handle when the client is available."""
        client = self.get_client()
        if client is None:
            return None
        return client.table(table_name)


@lru_cache(maxsize=1)
def get_supabase_manager() -> SupabaseClientManager:
    """Return the shared Supabase manager."""
    return SupabaseClientManager()
