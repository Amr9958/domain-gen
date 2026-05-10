"""Direct tests for the resale scoring engine boundaries."""

from __future__ import annotations

from scoring import evaluate_domain
from scoring.score_profiles import get_profile


def test_spammy_low_trust_domain_is_rejected_with_context() -> None:
    appraisal = evaluate_domain("bestfreeagentai.xyz", profile="startup_brand", niche="Tech & SaaS")

    assert appraisal.rejected is True
    assert appraisal.grade == "Reject"
    assert "spam_pattern" in appraisal.flags
    assert "contains low-trust commercial wording" in appraisal.warnings


def test_contextual_keyword_terms_are_not_treated_as_spam() -> None:
    appraisal = evaluate_domain(
        "cryptovault.com",
        profile="startup_brand",
        niche="Crypto & Web3",
        user_keywords=("crypto", "vault"),
    )

    assert "spam_pattern" not in appraisal.flags
    assert appraisal.rejected is False


def test_legacy_profile_aliases_normalize_to_current_profiles() -> None:
    seo_appraisal = evaluate_domain("repairtools.com", profile="seo_exact", niche="Legal & Professional")
    ai_appraisal = evaluate_domain("nexaflow.ai", profile="ai_brand", niche="Tech & SaaS")

    assert seo_appraisal.profile == "seo_authority"
    assert get_profile("seo_exact").key == "seo_authority"
    assert seo_appraisal.grade == "A"
    assert "strong_exact_match_fit" in seo_appraisal.flags
    assert ai_appraisal.profile == "startup_brand"
    assert get_profile("ai_brand").key == "startup_brand"
    assert ai_appraisal.grade == "A"


def test_keyword_market_fit_bonus_can_lift_grade_boundary() -> None:
    without_keywords = evaluate_domain("cloudstack.com", profile="startup_brand", niche="Tech & SaaS")
    with_keywords = evaluate_domain(
        "cloudstack.com",
        profile="startup_brand",
        niche="Tech & SaaS",
        user_keywords=("cloud", "stack"),
    )

    assert without_keywords.grade == "A"
    assert with_keywords.grade == "A+"
    assert with_keywords.subscores["market_fit"] > without_keywords.subscores["market_fit"]


def test_poor_pronunciation_caps_score_and_rejects() -> None:
    appraisal = evaluate_domain("qzxjptm.com", profile="startup_brand", niche="Tech & SaaS")

    assert appraisal.rejected is True
    assert appraisal.final_score <= 45
    assert "poor_pronounceability" in appraisal.flags
    assert "pronunciation is very difficult" in appraisal.warnings


def test_weak_extension_caps_otherwise_strong_domain() -> None:
    appraisal = evaluate_domain(
        "payflow.xyz",
        profile="startup_brand",
        niche="Finance & Fintech",
        user_keywords=("pay",),
    )

    assert appraisal.subscores["extension_fit"] <= 3
    assert appraisal.final_score <= 70
    assert appraisal.grade == "B"
