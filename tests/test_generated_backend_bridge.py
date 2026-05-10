"""Smoke tests for the generated-domain backend bridge job."""

from __future__ import annotations

import json
from pathlib import Path

from jobs.sync_generated_opportunities_to_backend import (
    domain_opportunity_from_row,
    normalize_domain,
    read_domain_opportunities,
    run_sync,
)


def test_read_domain_opportunities_dedupes_latest_rows(tmp_path) -> None:
    input_path = tmp_path / "domain_ideas.jsonl"
    rows = [
        {"source_theme": "agents", "domain_name": "atlasai", "extension": "com", "score": 72},
        {"source_theme": "agents", "domain_name": "atlasai", "extension": "com", "score": 81},
        {"source_theme": "agents", "domain_name": "orbitflow", "extension": ".io", "score": 64},
    ]
    input_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    opportunities = list(read_domain_opportunities(input_path))

    assert len(opportunities) == 2
    assert opportunities[0].domain_name == "atlasai"
    assert opportunities[0].score == 81
    assert normalize_domain(opportunities[1]) == ("orbitflow.io", "orbitflow", "io")


def test_run_sync_missing_input_is_noop() -> None:
    summary = run_sync(input_path=Path("/tmp/domain-gen-missing-domain-ideas.jsonl"), correlation_id="smoke-test")

    assert summary.read == 0
    assert summary.synced == 0


def test_domain_opportunity_from_row_accepts_scalar_risk_notes() -> None:
    opportunity = domain_opportunity_from_row(
        {
            "domain_name": "atlasai",
            "extension": "com",
            "risk_notes": "trademark review needed",
            "recommendation": "shortlist",
        }
    )

    assert opportunity.risk_notes == ("trademark review needed",)
