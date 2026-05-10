"""Derived-signal construction and persistence services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from domain_intel.db.base import utc_now
from domain_intel.db.models import DerivedSignal


@dataclass(frozen=True)
class DerivedSignalDraft:
    """Write-ready derived signal payload."""

    signal_type: str
    signal_key: str
    signal_value_json: dict[str, Any]
    confidence_score: Decimal | None = None
    input_fact_ids: tuple[UUID, ...] = field(default_factory=tuple)
    input_signal_ids: tuple[UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LegacyOpportunitySignalInput:
    """Legacy generated-domain fields that can become derived signals."""

    score: float = 0.0
    grade: str = ""
    scoring_profile: str = ""
    value_estimate: str = ""
    source_theme: str = ""
    keyword: str = ""
    review_bucket: str = ""
    recommendation: str = ""
    style: str = ""
    risk_notes: tuple[str, ...] = field(default_factory=tuple)


class DerivedSignalService:
    """Build and persist derived signals without treating them as facts."""

    def __init__(self, algorithm_version: str) -> None:
        self.algorithm_version = algorithm_version

    def build_legacy_opportunity_drafts(
        self,
        opportunity: LegacyOpportunitySignalInput,
    ) -> list[DerivedSignalDraft]:
        """Convert legacy generated-domain output into derived signal drafts."""

        score = _clamp_score(opportunity.score)
        confidence = Decimal(str(round(score / 100, 4)))
        return [
            DerivedSignalDraft("legacy_scoring", "legacy_scoring_score", {"score": opportunity.score}, confidence),
            DerivedSignalDraft("legacy_scoring", "legacy_scoring_grade", {"grade": opportunity.grade}, confidence),
            DerivedSignalDraft(
                "legacy_scoring",
                "legacy_scoring_profile",
                {"profile": opportunity.scoring_profile},
                confidence,
            ),
            DerivedSignalDraft(
                "legacy_scoring",
                "legacy_scoring_value_band",
                {"value_band": opportunity.value_estimate},
                confidence,
            ),
            DerivedSignalDraft(
                "legacy_generation",
                "legacy_generation_theme",
                {"theme": opportunity.source_theme},
                Decimal("0.7000"),
            ),
            DerivedSignalDraft(
                "legacy_generation",
                "legacy_generation_keyword",
                {"keyword": opportunity.keyword},
                Decimal("0.7000"),
            ),
            DerivedSignalDraft(
                "legacy_generation",
                "legacy_generation_review_bucket",
                {"bucket": opportunity.review_bucket},
                Decimal("0.7000"),
            ),
            DerivedSignalDraft(
                "legacy_generation",
                "legacy_generation_recommendation",
                {"recommendation": opportunity.recommendation},
                Decimal("0.7000"),
            ),
            DerivedSignalDraft(
                "legacy_generation",
                "legacy_generation_style",
                {"style": opportunity.style},
                Decimal("0.6500"),
            ),
            DerivedSignalDraft(
                "legacy_risk",
                "legacy_generation_risk_notes",
                {"risk_notes": list(opportunity.risk_notes)},
                Decimal("0.6000"),
            ),
        ]

    def upsert_domain_signals(
        self,
        *,
        session: Session,
        domain_id: UUID,
        drafts: Iterable[DerivedSignalDraft],
        auction_id: UUID | None = None,
        generated_at: datetime | None = None,
    ) -> list[DerivedSignal]:
        """Create or update latest domain-scoped derived signals."""

        generated_at = generated_at or utc_now()
        rows: list[DerivedSignal] = []
        for draft in drafts:
            row = self.latest_signal(
                session=session,
                domain_id=domain_id,
                signal_type=draft.signal_type,
                signal_key=draft.signal_key,
            )
            if row is None:
                row = DerivedSignal(
                    domain_id=domain_id,
                    auction_id=auction_id,
                    signal_type=draft.signal_type,
                    signal_key=draft.signal_key,
                    signal_value_json=draft.signal_value_json,
                    input_fact_ids=list(draft.input_fact_ids),
                    input_signal_ids=list(draft.input_signal_ids),
                    algorithm_version=self.algorithm_version,
                    confidence_score=draft.confidence_score,
                    generated_at=generated_at,
                )
                session.add(row)
            else:
                row.auction_id = auction_id
                row.signal_value_json = draft.signal_value_json
                row.input_fact_ids = list(draft.input_fact_ids)
                row.input_signal_ids = list(draft.input_signal_ids)
                row.confidence_score = draft.confidence_score
                row.generated_at = generated_at
            rows.append(row)
        session.flush()
        return rows

    def latest_signal(
        self,
        *,
        session: Session,
        domain_id: UUID,
        signal_type: str,
        signal_key: str,
    ) -> DerivedSignal | None:
        """Return the latest matching signal for this service version."""

        return session.scalar(
            select(DerivedSignal)
            .where(
                DerivedSignal.domain_id == domain_id,
                DerivedSignal.signal_type == signal_type,
                DerivedSignal.signal_key == signal_key,
                DerivedSignal.algorithm_version == self.algorithm_version,
            )
            .order_by(desc(DerivedSignal.generated_at))
            .limit(1)
        )


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value or 0.0)))
