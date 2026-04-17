"""Repositories for collected and processed signal items."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from config import get_settings
from core.logging import get_logger
from integrations import get_supabase_manager
from jobs.runtime import JobContext
from processors.clustering import ClusteredContentItem


logger = get_logger("repositories.signals")


class SignalRepository(Protocol):
    """Persistence contract for signal pipeline outputs."""

    def save_run(self, job: JobContext) -> None:
        """Persist run metadata."""

    def save_raw_items(self, items: list[dict[str, Any]]) -> None:
        """Persist raw collected items."""

    def save_processed_items(self, items: list[ClusteredContentItem]) -> None:
        """Persist processed items."""


class LocalSignalRepository:
    """Local JSONL fallback used when Supabase is not enabled."""

    def __init__(self) -> None:
        self.base_dir = get_settings().data_dir / "signals"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, default=str, ensure_ascii=True) + "\n")

    def save_run(self, job: JobContext) -> None:
        self._append_jsonl(self.base_dir / "runs.jsonl", [asdict(job.run)])

    def save_raw_items(self, items: list[dict[str, Any]]) -> None:
        self._append_jsonl(self.base_dir / "raw_items.jsonl", items)

    def save_processed_items(self, items: list[ClusteredContentItem]) -> None:
        rows = [
            {
                **asdict(clustered.item),
                "cluster_key": clustered.cluster_key,
                "cluster_terms": list(clustered.cluster_terms),
            }
            for clustered in items
        ]
        self._append_jsonl(self.base_dir / "processed_items.jsonl", rows)


class SupabaseSignalRepository:
    """Supabase-backed signal repository for Phase 2 data."""

    def __init__(self) -> None:
        self.manager = get_supabase_manager()

    def save_run(self, job: JobContext) -> None:
        table = self.manager.table("runs")
        if table is None:
            return
        table.upsert(asdict(job.run), on_conflict="run_id").execute()

    def save_raw_items(self, items: list[dict[str, Any]]) -> None:
        table = self.manager.table("content_items")
        if table is None or not items:
            return
        table.upsert(items, on_conflict="content_hash").execute()

    def save_processed_items(self, items: list[ClusteredContentItem]) -> None:
        table = self.manager.table("content_items")
        if table is None or not items:
            return
        rows = []
        for clustered in items:
            payload = asdict(clustered.item)
            payload["tags"] = list(clustered.item.tags)
            payload["raw_payload"] = dict(clustered.item.raw_payload)
            payload["cluster_key"] = clustered.cluster_key
            rows.append(payload)
        table.upsert(rows, on_conflict="content_hash").execute()


def get_signal_repository() -> SignalRepository:
    """Return the active signal repository."""
    if get_settings().supabase_enabled:
        return SupabaseSignalRepository()
    return LocalSignalRepository()
