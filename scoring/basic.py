"""Compatibility wrappers around the production scoring engine."""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from scoring.scoring import evaluate_domain, pronounceability_score, split_domain, tokenize_name


DEFAULT_PROFILE = "startup_brand"
DEFAULT_TLD = ".com"


def is_pronounceable(name: str) -> bool:
    """Backwards-compatible pronounceability helper."""
    return pronounceability_score(name.lower(), [name.lower()]) >= 8


def score_domain(name: str, niche: str = "", word_banks: Mapping[str, Sequence[str]] | None = None) -> int:
    """Backwards-compatible score helper using the startup brand profile."""
    clean_name = re.sub(r"[^a-z]", "", name.lower())
    appraisal = evaluate_domain(f"{clean_name}{DEFAULT_TLD}", profile=DEFAULT_PROFILE, niche=niche, word_banks=word_banks)
    return appraisal.final_score


def appraise_name(
    name: str,
    niche: str = "",
    word_banks: Mapping[str, Sequence[str]] | None = None,
    profile: str = DEFAULT_PROFILE,
    tld: str = DEFAULT_TLD,
) -> dict:
    """Backwards-compatible appraisal wrapper returning a dict."""
    clean_name = re.sub(r"[^a-z]", "", name.lower())
    appraisal = evaluate_domain(f"{clean_name}{tld}", profile=profile, niche=niche, word_banks=word_banks)
    return {
        "tier": appraisal.tier,
        "value": appraisal.value,
        "score": appraisal.final_score,
        "grade": appraisal.grade,
        "profile": appraisal.profile,
        "explanation": appraisal.explanation,
        "flags": list(appraisal.flags),
        "warnings": list(appraisal.warnings),
        "subscores": dict(appraisal.subscores),
        "rejected": appraisal.rejected,
    }
