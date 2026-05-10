"""Tests for the pure Streamlit generation workflow extraction."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from scoring.interfaces import DomainAppraisal
from workflows.generation import GenerationWorkflowRequest, run_generation_workflow


TEST_WORD_BANKS = {
    "tech": ["agent", "flow", "data", "cloud"],
    "finance": ["pay", "vault", "fund", "ledger"],
    "common_modifiers": ["flow", "vault", "base"],
    "brandable_fragments": ["nexa", "agent"],
    "short_prefixes": ["neo", "zen"],
}


def _grade(score: int) -> str:
    if score >= 93:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 68:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def _fake_appraisal(domain: str, profile: str, score: int) -> DomainAppraisal:
    name, suffix = domain.rsplit(".", 1)
    grade = _grade(score)
    return DomainAppraisal(
        domain=domain,
        name=name,
        tld=f".{suffix}",
        profile=profile,
        final_score=score,
        grade=grade,
        tier="Test Tier",
        value="$1,000",
        subscores={
            "linguistic_quality": 20,
            "brandability": 20,
            "market_fit": 15,
            "extension_fit": 8,
            "liquidity": 8,
            "bonus_penalty": 0,
        },
        flags=[],
        warnings=[],
        explanation=f"{domain} scored {score}",
        rejected=False,
    )


def test_generation_workflow_dedupes_scores_buckets_history_and_injects_backend_map() -> None:
    def fake_generate_domains(**kwargs: Any) -> list[dict[str, Any]]:
        if kwargs["niche"] == "Tech & SaaS":
            return [
                {"name": "agentflow", "method": "compound", "source_name": "", "is_transformed": False},
                {"name": "data", "method": "short", "source_name": "", "is_transformed": False},
            ]
        return [
            {"name": "agentflow", "method": "brandable", "source_name": "", "is_transformed": False},
            {"name": "payvault", "method": "compound", "source_name": "", "is_transformed": False},
        ]

    def fake_evaluate_domain(domain: str, profile: str, **_: Any) -> DomainAppraisal:
        return _fake_appraisal(
            domain,
            profile,
            {
                "data.com": 96,
                "agentflow.com": 84,
                "payvault.com": 72,
            }[domain],
        )

    backend_valuation = {"status": "valued", "estimated_value_min": 1000, "estimated_value_max": 2500}
    result = run_generation_workflow(
        GenerationWorkflowRequest(
            niches=["Tech & SaaS", "Finance & Fintech"],
            generation_styles=["auto"],
            keywords="agent, pay, data",
            geo_context="",
            num_per_tier=5,
            extensions=[".com"],
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            backend_valuation_map={"agentflow.com": backend_valuation},
            generated_at=datetime(2026, 5, 9, 12, 30),
        ),
        generate_domains_fn=fake_generate_domains,
        evaluate_domain_fn=fake_evaluate_domain,
    )

    assert result.debug_snapshot.keyword_list == ["agent", "pay", "data"]
    assert result.debug_snapshot.candidate_count == 3
    assert result.debug_snapshot.method_counts == {"compound": 2, "short": 1}
    assert result.debug_snapshot.sample_candidates == ["agentflow", "data", "payvault"]

    domains = [appraisal["domain"] for appraisal in result.displayed_appraisals]
    assert sorted(domains) == ["agentflow.com", "data.com", "payvault.com"]
    assert domains.count("agentflow.com") == 1

    data_appraisal = result.categories["A+"][0]
    agent_appraisal = result.categories["A"][0]
    pay_appraisal = result.categories["B"][0]
    assert data_appraisal["profile"] == "flip_fast"
    assert agent_appraisal["niche"] == "Tech & SaaS"
    assert agent_appraisal["backend_valuation"] == backend_valuation
    assert pay_appraisal["niche"] == "Finance & Fintech"

    history_by_domain = {row["Domain"]: row for row in result.history_rows}
    assert history_by_domain["data.com"]["Profile"] == "Flip Fast (auto)"
    assert history_by_domain["agentflow.com"]["Profile"] == "Startup Brand (auto)"
    assert history_by_domain["payvault.com"]["Niche"] == "Finance & Fintech"
    assert history_by_domain["payvault.com"]["Date"] == "2026-05-09 12:30"


def test_generation_workflow_preserves_transformed_source_delta() -> None:
    def fake_generate_domains(**_: Any) -> list[dict[str, Any]]:
        return [
            {"name": "agentbase", "method": "keyword", "source_name": "", "is_transformed": False},
            {"name": "agentflow", "method": "compound", "source_name": "agentbase", "is_transformed": True},
        ]

    def fake_evaluate_domain(domain: str, profile: str, **_: Any) -> DomainAppraisal:
        return _fake_appraisal(domain, profile, {"agentbase.com": 70, "agentflow.com": 84}[domain])

    result = run_generation_workflow(
        GenerationWorkflowRequest(
            niches=["Tech & SaaS"],
            generation_styles=["auto"],
            keywords="agent",
            geo_context="",
            num_per_tier=5,
            extensions=[".com"],
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
        ),
        generate_domains_fn=fake_generate_domains,
        evaluate_domain_fn=fake_evaluate_domain,
    )

    agentflow = result.categories["A"][0]
    assert agentflow["domain"] == "agentflow.com"
    assert agentflow["source_domain"] == "agentbase.com"
    assert agentflow["improvement_delta"] == 14
