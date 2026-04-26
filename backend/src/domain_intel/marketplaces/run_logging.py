"""Scrape run logging hooks.

Production jobs can implement ``ScrapeRunLogger`` with database-backed writes to
``ingest_runs.metrics_json``. The adapter only depends on this protocol so it
can be tested without a database session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol

from domain_intel.marketplaces.schemas import json_compatible, utc_isoformat


@dataclass
class ScrapeRunMetrics:
    """Mutable scrape metrics captured during one adapter run."""

    pages_attempted: int = 0
    pages_succeeded: int = 0
    items_seen: int = 0
    items_emitted: int = 0
    duplicate_items: int = 0
    errors: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages_attempted": self.pages_attempted,
            "pages_succeeded": self.pages_succeeded,
            "items_seen": self.items_seen,
            "items_emitted": self.items_emitted,
            "duplicate_items": self.duplicate_items,
            "errors": self.errors,
            "started_at": utc_isoformat(self.started_at) if self.started_at else None,
            "completed_at": utc_isoformat(self.completed_at) if self.completed_at else None,
        }


class ScrapeRunLogger(Protocol):
    """Adapter logging protocol for scrape or ingest run observability."""

    def run_started(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        adapter_version: str,
        parser_version: str,
        started_at: datetime,
    ) -> None:
        """Record the beginning of a scrape run."""

    def page_started(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        url: str,
        page_cursor: str | None,
        started_at: datetime,
    ) -> None:
        """Record the beginning of a page fetch."""

    def page_completed(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        url: str,
        item_count: int,
        emitted_count: int,
        duplicate_count: int,
        next_page_cursor: str | None,
        completed_at: datetime,
    ) -> None:
        """Record a successful page fetch and parse."""

    def error_recorded(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        error_code: str,
        error_summary: str,
        details: Mapping[str, Any],
        occurred_at: datetime,
    ) -> None:
        """Record a non-fatal or fatal adapter error."""

    def run_completed(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        status: str,
        metrics: Mapping[str, Any],
        completed_at: datetime,
    ) -> None:
        """Record run completion status and metrics."""


class NoopScrapeRunLogger:
    """Logger implementation for callers that do not persist scrape metrics yet."""

    def run_started(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        adapter_version: str,
        parser_version: str,
        started_at: datetime,
    ) -> None:
        _ = ingest_run_id, source_name, adapter_version, parser_version, started_at

    def page_started(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        url: str,
        page_cursor: str | None,
        started_at: datetime,
    ) -> None:
        _ = ingest_run_id, source_name, url, page_cursor, started_at

    def page_completed(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        url: str,
        item_count: int,
        emitted_count: int,
        duplicate_count: int,
        next_page_cursor: str | None,
        completed_at: datetime,
    ) -> None:
        _ = (
            ingest_run_id,
            source_name,
            url,
            item_count,
            emitted_count,
            duplicate_count,
            next_page_cursor,
            completed_at,
        )

    def error_recorded(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        error_code: str,
        error_summary: str,
        details: Mapping[str, Any],
        occurred_at: datetime,
    ) -> None:
        _ = ingest_run_id, source_name, error_code, error_summary, details, occurred_at

    def run_completed(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        status: str,
        metrics: Mapping[str, Any],
        completed_at: datetime,
    ) -> None:
        _ = ingest_run_id, source_name, status, metrics, completed_at


class InMemoryScrapeRunLogger(NoopScrapeRunLogger):
    """Test logger that records events and aggregate metrics."""

    def __init__(self) -> None:
        self.metrics = ScrapeRunMetrics()
        self.events: list[dict[str, Any]] = []

    def run_started(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        adapter_version: str,
        parser_version: str,
        started_at: datetime,
    ) -> None:
        self.metrics.started_at = started_at
        self.events.append(
            {
                "event": "run_started",
                "ingest_run_id": ingest_run_id,
                "source_name": source_name,
                "adapter_version": adapter_version,
                "parser_version": parser_version,
                "started_at": utc_isoformat(started_at),
            }
        )

    def page_started(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        url: str,
        page_cursor: str | None,
        started_at: datetime,
    ) -> None:
        self.metrics.pages_attempted += 1
        self.events.append(
            {
                "event": "page_started",
                "ingest_run_id": ingest_run_id,
                "source_name": source_name,
                "url": url,
                "page_cursor": page_cursor,
                "started_at": utc_isoformat(started_at),
            }
        )

    def page_completed(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        url: str,
        item_count: int,
        emitted_count: int,
        duplicate_count: int,
        next_page_cursor: str | None,
        completed_at: datetime,
    ) -> None:
        self.metrics.pages_succeeded += 1
        self.metrics.items_seen += item_count
        self.metrics.items_emitted += emitted_count
        self.metrics.duplicate_items += duplicate_count
        self.events.append(
            {
                "event": "page_completed",
                "ingest_run_id": ingest_run_id,
                "source_name": source_name,
                "url": url,
                "item_count": item_count,
                "emitted_count": emitted_count,
                "duplicate_count": duplicate_count,
                "next_page_cursor": next_page_cursor,
                "completed_at": utc_isoformat(completed_at),
            }
        )

    def error_recorded(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        error_code: str,
        error_summary: str,
        details: Mapping[str, Any],
        occurred_at: datetime,
    ) -> None:
        self.metrics.errors += 1
        self.events.append(
            {
                "event": "error_recorded",
                "ingest_run_id": ingest_run_id,
                "source_name": source_name,
                "error_code": error_code,
                "error_summary": error_summary,
                "details": json_compatible(details),
                "occurred_at": utc_isoformat(occurred_at),
            }
        )

    def run_completed(
        self,
        *,
        ingest_run_id: str,
        source_name: str,
        status: str,
        metrics: Mapping[str, Any],
        completed_at: datetime,
    ) -> None:
        self.metrics.completed_at = completed_at
        self.events.append(
            {
                "event": "run_completed",
                "ingest_run_id": ingest_run_id,
                "source_name": source_name,
                "status": status,
                "metrics": json_compatible(metrics),
                "completed_at": utc_isoformat(completed_at),
            }
        )
