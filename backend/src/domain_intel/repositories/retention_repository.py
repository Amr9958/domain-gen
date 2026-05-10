"""SQLAlchemy repository for approved retention cleanup."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from domain_intel.db.models import RawAuctionItem, WebsiteCheck
from domain_intel.repositories.base import BaseRepository
from domain_intel.services.retention_service import RetentionRepositoryProtocol


class RetentionRepository(BaseRepository, RetentionRepositoryProtocol):
    """Apply retention cleanup against persisted raw and metadata tables."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def scrub_raw_marketplace_payloads(self, cutoff: datetime, purged_at: datetime) -> int:
        """Scrub raw payload content while preserving the raw observation row."""

        result = self.session.execute(
            update(RawAuctionItem)
            .where(RawAuctionItem.captured_at < cutoff)
            .values(
                raw_payload_json={
                    "retention_status": "purged",
                    "purged_at": purged_at.isoformat(),
                    "policy": "raw_marketplace_payload_30_days",
                },
                raw_artifact_uri=None,
            )
        )
        self.session.commit()
        return int(result.rowcount or 0)

    def delete_website_checks(self, cutoff: datetime) -> int:
        """Delete website-check metadata older than the approved retention window."""

        result = self.session.execute(delete(WebsiteCheck).where(WebsiteCheck.checked_at < cutoff))
        self.session.commit()
        return int(result.rowcount or 0)
