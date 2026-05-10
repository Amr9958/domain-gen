"""Unit tests for approved retention cleanup policy."""

from __future__ import annotations

from datetime import datetime, timezone

from domain_intel.services.retention_service import RetentionCleanupPolicy, RetentionCleanupService


def test_retention_cleanup_uses_approved_cutoffs() -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    repository = FakeRetentionRepository()
    service = RetentionCleanupService(repository, RetentionCleanupPolicy())

    result = service.run_cleanup(now)

    assert result.raw_marketplace_payloads_scrubbed == 3
    assert result.website_checks_deleted == 2
    assert repository.raw_cutoff.isoformat() == "2026-04-03T12:00:00+00:00"
    assert repository.website_cutoff.isoformat() == "2026-02-02T12:00:00+00:00"
    assert repository.purged_at == now


class FakeRetentionRepository:
    def __init__(self) -> None:
        self.raw_cutoff = None
        self.website_cutoff = None
        self.purged_at = None

    def scrub_raw_marketplace_payloads(self, cutoff: datetime, purged_at: datetime) -> int:
        self.raw_cutoff = cutoff
        self.purged_at = purged_at
        return 3

    def delete_website_checks(self, cutoff: datetime) -> int:
        self.website_cutoff = cutoff
        return 2
