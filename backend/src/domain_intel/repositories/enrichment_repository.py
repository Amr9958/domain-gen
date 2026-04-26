"""Persistence support for domain enrichment workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import desc, select

from domain_intel.core.enums import EnrichmentStatus
from domain_intel.db.models import DerivedSignal, Domain, EnrichmentRun, VerifiedFact, WebsiteCheck
from domain_intel.enrichment.contracts import DerivedSignalDraft, VerifiedFactDraft, WebsiteCheckDraft
from domain_intel.repositories.base import BaseRepository


class EnrichmentRepository(BaseRepository):
    """Repository for enrichment runs, facts, website checks, and signals."""

    def get_domain(self, domain_id: UUID) -> Domain | None:
        """Load a canonical domain row."""

        return self.session.get(Domain, domain_id)

    def latest_fact_observed_at(self, domain_id: UUID, fact_type: str) -> datetime | None:
        """Return the latest observed time for a fact type."""

        statement = (
            select(VerifiedFact.observed_at)
            .where(VerifiedFact.domain_id == domain_id, VerifiedFact.fact_type == fact_type)
            .order_by(desc(VerifiedFact.observed_at))
            .limit(1)
        )
        return self.session.scalar(statement)

    def latest_website_check_at(self, domain_id: UUID) -> datetime | None:
        """Return the latest website check timestamp."""

        statement = (
            select(WebsiteCheck.checked_at)
            .where(WebsiteCheck.domain_id == domain_id)
            .order_by(desc(WebsiteCheck.checked_at))
            .limit(1)
        )
        return self.session.scalar(statement)

    def create_enrichment_run(
        self,
        *,
        domain_id: UUID,
        run_type: str,
        provider: str,
        status: EnrichmentStatus,
        started_at: datetime,
    ) -> EnrichmentRun:
        """Create and flush an enrichment run row."""

        run = EnrichmentRun(
            domain_id=domain_id,
            run_type=run_type,
            provider=provider,
            status=status.value,
            started_at=started_at,
            created_fact_ids=[],
        )
        self.session.add(run)
        self.session.flush()
        return run

    def update_enrichment_run(
        self,
        run: EnrichmentRun,
        *,
        status: EnrichmentStatus,
        completed_at: datetime | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
        created_fact_ids: Optional[Iterable[UUID]] = None,
    ) -> None:
        """Update an existing enrichment run and flush changes."""

        run.status = status.value
        run.completed_at = completed_at
        run.error_code = error_code
        run.error_summary = error_summary
        if created_fact_ids is not None:
            run.created_fact_ids = list(created_fact_ids)
        self.session.add(run)
        self.session.flush()

    def create_verified_facts(self, domain_id: UUID, drafts: Iterable[VerifiedFactDraft]) -> List[VerifiedFact]:
        """Persist verified facts and return ORM rows with generated IDs."""

        rows: List[VerifiedFact] = []
        for draft in drafts:
            row = VerifiedFact(
                domain_id=domain_id,
                auction_id=None,
                fact_type=draft.fact_type,
                fact_key=draft.fact_key,
                fact_value_json=draft.fact_value_json,
                source_system=draft.source_system,
                source_url=draft.source_url,
                evidence_ref=draft.evidence_ref,
                observed_at=draft.observed_at,
                valid_from=draft.valid_from,
                valid_until=draft.valid_until,
                provider_version=draft.provider_version,
                parser_version=draft.parser_version,
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return rows

    def create_derived_signals(self, domain_id: UUID, drafts: Iterable[DerivedSignalDraft]) -> List[DerivedSignal]:
        """Persist derived signals and return ORM rows with generated IDs."""

        rows: List[DerivedSignal] = []
        for draft in drafts:
            row = DerivedSignal(
                domain_id=domain_id,
                auction_id=None,
                signal_type=draft.signal_type,
                signal_key=draft.signal_key,
                signal_value_json=draft.signal_value_json,
                input_fact_ids=draft.input_fact_ids,
                input_signal_ids=draft.input_signal_ids,
                algorithm_version=draft.algorithm_version,
                confidence_score=draft.confidence_score,
                generated_at=draft.generated_at,
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return rows

    def create_website_check(self, domain_id: UUID, draft: WebsiteCheckDraft) -> WebsiteCheck:
        """Persist a website check row with linked created fact IDs."""

        row = WebsiteCheck(
            domain_id=domain_id,
            checked_at=draft.checked_at,
            start_url=draft.start_url,
            final_url=draft.final_url,
            http_status=draft.http_status,
            redirect_count=draft.redirect_count,
            tls_valid=draft.tls_valid,
            title=draft.title,
            content_hash=draft.content_hash,
            technology_json=draft.technology_json,
            created_fact_ids=draft.created_fact_ids,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def commit(self) -> None:
        """Commit the current transaction."""

        self.session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""

        self.session.rollback()
