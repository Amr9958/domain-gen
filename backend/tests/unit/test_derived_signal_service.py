"""Derived signal service tests."""

from __future__ import annotations

from decimal import Decimal

from domain_intel.services.derived_signal_service import (
    DerivedSignalService,
    LegacyOpportunitySignalInput,
)


def test_legacy_opportunity_outputs_are_derived_signal_drafts() -> None:
    service = DerivedSignalService(algorithm_version="test-signals")

    drafts = service.build_legacy_opportunity_drafts(
        LegacyOpportunitySignalInput(
            score=82,
            grade="A",
            scoring_profile="exact_match",
            value_estimate="$1k-$3k",
            source_theme="AI workflow",
            keyword="workflow",
            review_bucket="shortlist",
            recommendation="buy",
            style="exact",
            risk_notes=("No obvious risk.",),
        )
    )

    keys = {draft.signal_key for draft in drafts}
    assert "legacy_scoring_score" in keys
    assert "legacy_generation_theme" in keys
    assert "legacy_generation_risk_notes" in keys
    assert all(draft.input_fact_ids == tuple() for draft in drafts)
    assert all(draft.input_signal_ids == tuple() for draft in drafts)
    score_draft = next(draft for draft in drafts if draft.signal_key == "legacy_scoring_score")
    assert score_draft.signal_type == "legacy_scoring"
    assert score_draft.signal_value_json == {"score": 82}
    assert score_draft.confidence_score == Decimal("0.82")
