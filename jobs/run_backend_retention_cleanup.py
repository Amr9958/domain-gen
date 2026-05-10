"""Run approved backend retention cleanup tasks."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from domain_intel.db.session import SessionLocal  # noqa: E402
from domain_intel.repositories.retention_repository import RetentionRepository  # noqa: E402
from domain_intel.services.retention_service import (  # noqa: E402
    RetentionCleanupPolicy,
    RetentionCleanupResult,
    RetentionCleanupService,
)


LOGGER = logging.getLogger("domain_intel.retention_cleanup")


@dataclass(frozen=True)
class RetentionJobSummary:
    """Summary returned by the backend retention cleanup job."""

    raw_marketplace_payloads_scrubbed: int
    website_checks_deleted: int

    @classmethod
    def from_result(cls, result: RetentionCleanupResult) -> "RetentionJobSummary":
        return cls(
            raw_marketplace_payloads_scrubbed=result.raw_marketplace_payloads_scrubbed,
            website_checks_deleted=result.website_checks_deleted,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "raw_marketplace_payloads_scrubbed": self.raw_marketplace_payloads_scrubbed,
            "website_checks_deleted": self.website_checks_deleted,
        }


def run_cleanup(
    *,
    now: datetime | None = None,
    raw_marketplace_payload_days: int = 30,
    website_metadata_days: int = 90,
    correlation_id: str | None = None,
) -> RetentionJobSummary:
    """Run backend retention cleanup against the configured database."""

    correlation_id = correlation_id or str(uuid4())
    cleanup_time = now or datetime.now(timezone.utc)
    LOGGER.info(
        "retention_cleanup_started",
        extra={
            "correlation_id": correlation_id,
            "raw_marketplace_payload_days": raw_marketplace_payload_days,
            "website_metadata_days": website_metadata_days,
        },
    )
    with SessionLocal() as session:
        service = RetentionCleanupService(
            RetentionRepository(session),
            RetentionCleanupPolicy(
                raw_marketplace_payload_days=raw_marketplace_payload_days,
                website_metadata_days=website_metadata_days,
            ),
        )
        summary = RetentionJobSummary.from_result(service.run_cleanup(cleanup_time))
    LOGGER.info(
        "retention_cleanup_finished",
        extra={"correlation_id": correlation_id, **summary.as_dict()},
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-marketplace-payload-days", type=int, default=30)
    parser.add_argument("--website-metadata-days", type=int, default=90)
    args = parser.parse_args()
    summary = run_cleanup(
        raw_marketplace_payload_days=args.raw_marketplace_payload_days,
        website_metadata_days=args.website_metadata_days,
    )
    print(summary.as_dict())


if __name__ == "__main__":
    main()
