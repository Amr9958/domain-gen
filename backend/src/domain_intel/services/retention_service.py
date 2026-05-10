"""Retention cleanup services for raw payloads and operational metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


@dataclass(frozen=True)
class RetentionCleanupPolicy:
    """Retention windows for approved v1 data cleanup."""

    raw_marketplace_payload_days: int = 30
    website_metadata_days: int = 90


@dataclass(frozen=True)
class RetentionCleanupResult:
    """Counts returned by retention cleanup runs."""

    raw_marketplace_payloads_scrubbed: int
    website_checks_deleted: int


class RetentionRepositoryProtocol(Protocol):
    """Persistence boundary for retention cleanup."""

    def scrub_raw_marketplace_payloads(self, cutoff: datetime, purged_at: datetime) -> int:
        """Remove retained raw payload/artifact content before the cutoff."""

    def delete_website_checks(self, cutoff: datetime) -> int:
        """Delete website-check metadata before the cutoff."""


class RetentionCleanupService:
    """Apply approved retention windows without mutating facts or valuations."""

    def __init__(
        self,
        repository: RetentionRepositoryProtocol,
        policy: RetentionCleanupPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.policy = policy or RetentionCleanupPolicy()

    def run_cleanup(self, now: datetime) -> RetentionCleanupResult:
        """Run all approved retention cleanup tasks."""

        raw_cutoff = now - timedelta(days=self.policy.raw_marketplace_payload_days)
        website_cutoff = now - timedelta(days=self.policy.website_metadata_days)
        return RetentionCleanupResult(
            raw_marketplace_payloads_scrubbed=self.repository.scrub_raw_marketplace_payloads(raw_cutoff, now),
            website_checks_deleted=self.repository.delete_website_checks(website_cutoff),
        )
