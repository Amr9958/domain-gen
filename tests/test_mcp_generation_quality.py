"""Quality checks for treating MCP as a normal domain-generation keyword."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from unittest.mock import patch

from generator import _style_bucket, generate_domains
from scoring import evaluate_domain
from scoring.hard_filters import TRADEMARK_TERMS
from utils.word_banks import load_word_banks
from workflows.generation import GenerationWorkflowRequest, run_generation_workflow


def test_mcp_keyword_offline_generation_has_diverse_clean_candidates() -> None:
    word_banks = load_word_banks()
    candidates = generate_domains(
        niche="Tech & SaaS",
        use_llm=False,
        word_banks=word_banks,
        keywords_str="mcp",
        num_per_tier=12,
    )

    names = [str(candidate["name"]) for candidate in candidates]
    styles = Counter(_style_bucket(str(candidate["method"])) for candidate in candidates)
    roots = Counter(name[:4] for name in names)
    appraisals = [
        evaluate_domain(
            f"{name}.com",
            profile="startup_brand",
            niche="Tech & SaaS",
            word_banks=word_banks,
            user_keywords=("mcp",),
        )
        for name in names
    ]

    assert len(candidates) >= 40
    assert len(set(names)) == len(names)
    assert len(styles) >= 4
    assert max(roots.values()) <= 6
    assert all("mcp" in name for name in names)
    assert not {
        "exact_support",
        "compound_support",
        "short_support",
        "invented_random",
    } & {str(candidate["method"]) for candidate in candidates}
    assert "cvcv" not in {str(candidate.get("source_name") or "") for candidate in candidates}
    assert not [name for name in names for term in TRADEMARK_TERMS if term in name]
    assert not [appraisal.domain for appraisal in appraisals if "spam_pattern" in appraisal.flags]
    assert sum(appraisal.rejected for appraisal in appraisals) == 0


def test_mcp_agent_workflow_offline_generation_expands_pool_and_preserves_keyword_sources() -> None:
    word_banks = load_word_banks()
    candidates = generate_domains(
        niche="Tech & SaaS",
        use_llm=False,
        word_banks=word_banks,
        keywords_str="mcp, agent, workflow",
        num_per_tier=12,
    )

    names = [str(candidate["name"]) for candidate in candidates]
    source_names = {str(candidate.get("source_name") or "") for candidate in candidates}
    styles = Counter(_style_bucket(str(candidate["method"])) for candidate in candidates)

    assert len(candidates) >= 40
    assert len(styles) >= 4
    assert "mcp" in source_names
    assert all("mcp" in name for name in names)


def test_mcp_generation_workflow_scores_once_and_adds_auto_profiles() -> None:
    word_banks = load_word_banks()
    result = run_generation_workflow(
        GenerationWorkflowRequest(
            niches=["Tech & SaaS"],
            generation_styles=["auto"],
            keywords="mcp",
            geo_context="",
            num_per_tier=6,
            extensions=[".com"],
            use_llm=False,
            word_banks=word_banks,
            generated_at=datetime(2026, 5, 10, 12, 0),
        )
    )

    displayed_domains = [appraisal["domain"] for appraisal in result.displayed_appraisals]
    history_by_domain = {row["Domain"]: row for row in result.history_rows}

    assert result.debug_snapshot.keyword_list == ["mcp"]
    assert result.debug_snapshot.candidate_count >= 40
    assert displayed_domains
    assert len(displayed_domains) == len(set(displayed_domains))
    assert all(history_by_domain[domain]["Profile"].endswith("(auto)") for domain in displayed_domains)


@patch("providers.llm.call_llm")
def test_mcp_openrouter_mocked_suggestions_merge_with_offline_candidates(mocked_call_llm) -> None:
    mocked_call_llm.return_value = (
        '{"domains": ['
        '{"name": "MCPAlo.com", "style": "invented"}, '
        '{"domain": "MCPOra.ai", "category": "brandable"}, '
        '{"domain": "CleanSignal.com", "category": "brandable"}, '
        '{"domain": "MCPAlo.com", "style": "invented"}'
        "]}"
    )
    word_banks = load_word_banks()

    candidates = generate_domains(
        niche="Tech & SaaS",
        use_llm=True,
        word_banks=word_banks,
        requested_styles=["brandable", "invented"],
        keywords_str="mcp",
        num_per_tier=8,
    )

    names = [str(candidate["name"]) for candidate in candidates]
    assert "mcpalo" in names
    assert "mcpora" in names
    assert "cleansignal" not in names
    assert all("mcp" in name for name in names)
    assert names.count("mcpalo") == 1
    mocked_call_llm.assert_called_once()
    assert "Every returned domain name must visibly include `mcp`" in mocked_call_llm.call_args.args[0]
