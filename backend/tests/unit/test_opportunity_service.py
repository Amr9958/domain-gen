"""Unit tests for undervalued-auction screening."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from domain_intel.services.opportunity_service import (
    OpportunityService,
    UndervaluationCandidateInput,
    UndervaluationPolicy,
    ValueRangeValue,
)


def test_assess_candidate_returns_candidate_when_bid_is_below_thresholds() -> None:
    service = OpportunityService(FakeOpportunityRepository())
    candidate = _candidate_input()

    record = service.assess_candidate(candidate, UndervaluationPolicy())

    assert record.status == "candidate"
    assert record.bid_to_estimated_wholesale_ratio == "0.8000"
    assert record.bid_to_estimated_retail_ratio == "0.2667"


def test_assess_candidate_rejects_high_risk_inputs() -> None:
    service = OpportunityService(FakeOpportunityRepository())
    candidate = _candidate_input(risk_score=Decimal("0.80"))

    record = service.assess_candidate(candidate, UndervaluationPolicy())

    assert record.status == "rejected"
    assert "Risk score 0.80 exceeds 0.35." in record.reasons


class FakeOpportunityRepository:
    def list_candidates(self, query):
        return [], 0


def _candidate_input(risk_score: Decimal = Decimal("0.20")) -> UndervaluationCandidateInput:
    return UndervaluationCandidateInput(
        auction_id=uuid4(),
        domain_id=uuid4(),
        fqdn="atlasai.com",
        tld="com",
        marketplace_code="dynadot",
        auction_type="expired",
        auction_status="open",
        ends_at=datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc),
        current_bid_amount=Decimal("800"),
        currency="USD",
        bid_count=3,
        watchers_count=10,
        valuation_status="valued",
        confidence_level="high",
        estimated_retail_range=ValueRangeValue(low="2500.00", high="3500.00", currency="USD"),
        estimated_wholesale_range=ValueRangeValue(low="900.00", high="1100.00", currency="USD"),
        risk_score=risk_score,
        risk_flags=[],
    )
