"""Unit tests for valuation run persistence mapping."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from domain_intel.core.enums import ConfidenceLevel, ReasonDirection, ValuationStatus, ValueTier
from domain_intel.db.models import ValuationReasonCode, ValuationRun
from domain_intel.repositories.valuation_repository import PersistValuationRunCommand, ValuationRunRepository
from domain_intel.valuation.models import (
    ConfidenceAssessment,
    InvestmentRecommendation,
    ValuationReason,
    ValuationResult,
)


def test_valuation_repository_upserts_run_and_replaces_reason_codes() -> None:
    session = FakeSession()
    repository = ValuationRunRepository(session)
    domain_id = uuid4()
    classification_id = uuid4()
    signal_id = uuid4()

    first_run = repository.upsert_result(
        PersistValuationRunCommand(
            domain_id=domain_id,
            classification_result_id=classification_id,
            result=_valuation_result("strong_tld", "Strong TLD"),
            input_signal_ids=(signal_id,),
            algorithm_version="generated-domain-bridge-v1",
        )
    )

    assert first_run.domain_id == domain_id
    assert first_run.classification_result_id == classification_id
    assert first_run.status is ValuationStatus.VALUED
    assert first_run.estimated_value_min == Decimal("1000")
    assert first_run.input_signal_ids == [signal_id]
    assert first_run.algorithm_version == "generated-domain-bridge-v1"
    assert [item for item in session.added if isinstance(item, ValuationReasonCode)][0].code == "strong_tld"

    existing_reason = ValuationReasonCode(
        valuation_run_id=first_run.id,
        code="old_reason",
        label="Old reason",
        direction="neutral",
        evidence_refs_json=[],
        explanation="Old explanation.",
    )
    session.scalar_result = first_run
    session.reason_results = [existing_reason]

    second_run = repository.upsert_result(
        PersistValuationRunCommand(
            domain_id=domain_id,
            classification_result_id=classification_id,
            result=_valuation_result("clean_structure", "Clean structure"),
            input_signal_ids=(signal_id,),
            algorithm_version="generated-domain-bridge-v1",
        )
    )

    reason_codes = [item for item in session.added if isinstance(item, ValuationReasonCode)]
    assert second_run is first_run
    assert existing_reason in session.deleted
    assert reason_codes[-1].code == "clean_structure"
    assert reason_codes[-1].direction == "positive"
    assert reason_codes[-1].impact_weight == Decimal("0.25")


def _valuation_result(reason_code: str, reason_label: str) -> ValuationResult:
    return ValuationResult(
        status=ValuationStatus.VALUED,
        score=72,
        grade="B",
        confidence=ConfidenceAssessment(
            level=ConfidenceLevel.MEDIUM,
            score=0.66,
            rationale="Enough support for a persisted valuation.",
        ),
        value_tier=ValueTier.MEANINGFUL,
        domain_type=None,
        estimated_value_min=Decimal("1000"),
        estimated_value_max=Decimal("2500"),
        estimated_value_point=Decimal("1750"),
        wholesale_estimate=None,
        retail_estimate=None,
        bin_recommendation=None,
        minimum_acceptable_offer=None,
        hold_strategy="Hold for qualified end-user interest.",
        investment_recommendation=InvestmentRecommendation.HOLD,
        pricing_basis="unit-test",
        score_breakdown=(),
        risk_penalties=(),
        reason_codes=(
            ValuationReason(
                code=reason_code,
                label=reason_label,
                direction=ReasonDirection.POSITIVE,
                impact_weight=0.25,
                impact_amount=Decimal("250"),
                explanation="Reason persisted for traceability.",
            ),
        ),
        classification_result_id=None,
        algorithm_version="valuation-v1",
    )


class FakeScalars:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.scalar_result = None
        self.reason_results = []
        self.added = []
        self.deleted = []
        self.flush_count = 0

    def scalar(self, _statement):
        return self.scalar_result

    def scalars(self, _statement):
        return FakeScalars(self.reason_results)

    def add(self, item) -> None:
        self.added.append(item)

    def delete(self, item) -> None:
        self.deleted.append(item)

    def flush(self) -> None:
        self.flush_count += 1
        for item in self.added:
            if isinstance(item, ValuationRun) and item.id is None:
                item.id = uuid4()
