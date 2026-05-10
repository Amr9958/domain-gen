"""Smoke tests for backend retention cleanup job wiring."""

from __future__ import annotations

from datetime import datetime, timezone

from jobs import run_backend_retention_cleanup as retention_job


def test_retention_cleanup_job_returns_summary_with_configured_windows(monkeypatch) -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    fake_repository = FakeRetentionRepository()
    monkeypatch.setattr(retention_job, "SessionLocal", lambda: FakeSessionContext())
    monkeypatch.setattr(retention_job, "RetentionRepository", lambda session: fake_repository)

    summary = retention_job.run_cleanup(
        now=now,
        raw_marketplace_payload_days=7,
        website_metadata_days=14,
        correlation_id="retention-test",
    )

    assert summary.as_dict() == {
        "raw_marketplace_payloads_scrubbed": 4,
        "website_checks_deleted": 5,
    }
    assert fake_repository.raw_cutoff.isoformat() == "2026-04-26T12:00:00+00:00"
    assert fake_repository.website_cutoff.isoformat() == "2026-04-19T12:00:00+00:00"


class FakeSessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeRetentionRepository:
    def __init__(self) -> None:
        self.raw_cutoff = None
        self.website_cutoff = None

    def scrub_raw_marketplace_payloads(self, cutoff, purged_at) -> int:
        self.raw_cutoff = cutoff
        return 4

    def delete_website_checks(self, cutoff) -> int:
        self.website_cutoff = cutoff
        return 5
