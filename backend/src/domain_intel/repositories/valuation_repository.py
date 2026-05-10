"""Repository writes for persisted valuation runs and reason codes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select

from domain_intel.db.base import utc_now
from domain_intel.db.models import ValuationReasonCode, ValuationRun
from domain_intel.repositories.base import BaseRepository
from domain_intel.valuation.models import ValuationResult


@dataclass(frozen=True)
class PersistValuationRunCommand:
    """Inputs required to persist a deterministic valuation result."""

    domain_id: UUID
    result: ValuationResult
    auction_id: Optional[UUID] = None
    classification_result_id: Optional[UUID] = None
    input_fact_ids: tuple[UUID, ...] = ()
    input_signal_ids: tuple[UUID, ...] = ()
    algorithm_version: Optional[str] = None


class ValuationRunRepository(BaseRepository):
    """SQLAlchemy-backed valuation run writer."""

    def upsert_result(self, command: PersistValuationRunCommand) -> ValuationRun:
        """Create or update the latest valuation run for a domain/algorithm pair."""

        algorithm_version = command.algorithm_version or command.result.algorithm_version
        row = self.session.scalar(
            select(ValuationRun)
            .where(
                ValuationRun.domain_id == command.domain_id,
                ValuationRun.auction_id == command.auction_id,
                ValuationRun.algorithm_version == algorithm_version,
            )
            .order_by(desc(ValuationRun.created_at))
            .limit(1)
        )
        if row is None:
            row = ValuationRun(domain_id=command.domain_id)
            self.session.add(row)

        row.auction_id = command.auction_id
        row.classification_result_id = command.classification_result_id or command.result.classification_result_id
        row.status = command.result.status
        row.refusal_code = command.result.refusal_code
        row.refusal_reason = command.result.refusal_reason
        row.estimated_value_min = command.result.estimated_value_min
        row.estimated_value_max = command.result.estimated_value_max
        row.estimated_value_point = command.result.estimated_value_point
        row.currency = "USD"
        row.value_tier = command.result.value_tier
        row.confidence_level = command.result.confidence.level
        row.algorithm_version = algorithm_version
        row.input_fact_ids = list(command.input_fact_ids or command.result.input_fact_ids)
        row.input_signal_ids = list(command.input_signal_ids or command.result.input_signal_ids)
        row.created_at = utc_now()
        self.session.flush()

        self._replace_reason_codes(row, command.result)
        self.session.flush()
        return row

    def _replace_reason_codes(self, row: ValuationRun, result: ValuationResult) -> None:
        """Replace reason codes so repeated valuation writes stay idempotent."""

        existing_reasons = list(
            self.session.scalars(
                select(ValuationReasonCode).where(ValuationReasonCode.valuation_run_id == row.id)
            ).all()
        )
        for reason in existing_reasons:
            self.session.delete(reason)
        self.session.flush()

        for reason in result.reason_codes:
            self.session.add(
                ValuationReasonCode(
                    valuation_run_id=row.id,
                    code=reason.code,
                    label=reason.label,
                    direction=reason.direction.value,
                    impact_amount=reason.impact_amount,
                    impact_weight=Decimal(str(reason.impact_weight)),
                    evidence_refs_json=[
                        {
                            "type": ref.type,
                            "id": ref.id,
                            "source": ref.source,
                            "observed_at": ref.observed_at.isoformat() if ref.observed_at else None,
                        }
                        for ref in reason.evidence_refs
                    ],
                    explanation=reason.explanation,
                )
            )
