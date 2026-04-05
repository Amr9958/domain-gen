"""Core resale-focused domain scoring engine."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, Mapping, Sequence

from scoring.explanations import build_explanation
from scoring.hard_filters import apply_hard_filters
from scoring.interfaces import DomainAppraisal
from scoring.score_profiles import COMMON_GENERIC_TERMS, get_profile


VOWELS = set("aeiouy")
BAD_CLUSTERS = {
    "qx", "zx", "xq", "jq", "qj", "vv", "jj", "wx", "yyz", "ptm", "dtk", "ghtz", "rphn",
}
HARD_ENDINGS = {"q", "xj", "qz", "zx", "iums", "nessy"}
GOOD_SUFFIXES = {"labs", "forge", "flow", "stack", "cloud", "vault", "care", "clinic", "hub", "works", "base", "logic"}
BAD_PREFIXES = {"best", "cheap", "free", "top", "online", "my", "go", "up", "try", "use"}
GEO_HINTS = {
    "ny", "la", "sf", "us", "usa", "uk", "uae", "dubai", "cairo", "london", "texas", "miami",
    "metro", "city", "urban", "local", "east", "west", "north", "south",
}
NATURAL_HEADS = GOOD_SUFFIXES | {"pay", "data", "stream", "health", "realty", "tools", "software", "homes"}

NICHE_HINTS = {
    "Tech & AI": {"ai", "data", "cloud", "stack", "prompt", "model", "code", "bot", "agent"},
    "Finance & SaaS": {"pay", "fund", "vault", "wealth", "trade", "asset", "cash", "ledger"},
    "E-commerce": {"shop", "store", "cart", "pay", "deal", "flow", "market"},
    "Creative & Arts": {"studio", "pixel", "canvas", "design", "craft", "muse"},
    "Health & Wellness": {"health", "care", "clinic", "well", "med", "fit"},
    "Real Estate": {"home", "realty", "estate", "homes", "roof", "property"},
}


def split_domain(domain: str) -> tuple[str, str]:
    """Split a domain string into second-level name and TLD."""
    clean = domain.strip().lower()
    if "." not in clean:
        return clean, ""
    name, suffix = clean.rsplit(".", 1)
    return name, f".{suffix}"


@lru_cache(maxsize=4096)
def _segment_name_cached(name: str, lexicon_key: tuple[str, ...]) -> tuple[str, ...]:
    lexicon = list(lexicon_key)
    tokens: list[str] = []
    index = 0
    while index < len(name):
        match = next((token for token in lexicon if name.startswith(token, index)), None)
        if match:
            tokens.append(match)
            index += len(match)
            continue
        next_index = index + 1
        while next_index < len(name) and not any(name.startswith(token, next_index) for token in lexicon):
            next_index += 1
        tokens.append(name[index:next_index])
        index = next_index
    return tuple(token for token in tokens if token)


def tokenize_name(name: str, word_banks: Mapping[str, Sequence[str]] | None, profile: str) -> list[str]:
    """Split a lower-case name into likely semantic tokens."""
    profile_config = get_profile(profile)
    lexicon = {
        token.lower()
        for token in COMMON_GENERIC_TERMS
        | profile_config.favored_terms
        | profile_config.generic_terms
        | profile_config.head_terms
        | profile_config.modifier_terms
        | profile_config.commercial_terms
        | profile_config.local_terms
        | profile_config.exact_match_terms
        | GEO_HINTS
        if len(token) >= 2
    }
    if word_banks:
        for words in word_banks.values():
            for token in words:
                if len(token) >= 2:
                    lexicon.add(token.lower())
    ordered = tuple(sorted(lexicon, key=lambda item: (-len(item), item)))
    return list(_segment_name_cached(name, ordered))


def length_score(name: str) -> int:
    """Score raw length for resale viability."""
    length = len(name)
    if 5 <= length <= 8:
        return 8
    if 9 <= length <= 10:
        return 7
    if 11 <= length <= 12:
        return 5
    if 13 <= length <= 15:
        return 3
    if 4 <= length <= 16:
        return 2
    return 0


def pronounceability_score(name: str, tokens: Sequence[str]) -> int:
    """Estimate how easily the name can be spoken and remembered."""
    score = 12
    consonant_runs = re.findall(r"[bcdfghjklmnpqrstvwxz]{4,}", name)
    vowel_ratio = sum(char in VOWELS for char in name) / max(len(name), 1)

    score -= len(consonant_runs) * 3
    if vowel_ratio < 0.22 or vowel_ratio > 0.72:
        score -= 3
    if any(cluster in name for cluster in BAD_CLUSTERS):
        score -= 3
    if any(name.endswith(ending) for ending in HARD_ENDINGS):
        score -= 2
    if re.search(r"(.)\1{2,}", name):
        score -= 2
    if len(tokens) >= 2 and any(left[-1] == right[0] and left[-1] not in VOWELS for left, right in zip(tokens, tokens[1:])):
        score -= 2
    if len(tokens) == 1 and 5 <= len(name) <= 9 and consonant_runs == []:
        score += 1
    return max(0, min(score, 12))


def word_order_score(tokens: Sequence[str], profile: str) -> int:
    """Reward natural modifier-to-head ordering and penalize awkward reversals."""
    if len(tokens) <= 1:
        return 8 if tokens else 0

    profile_config = get_profile(profile)
    first = tokens[0]
    last = tokens[-1]
    score = 5

    if last in GOOD_SUFFIXES or last in profile_config.head_terms or last in NATURAL_HEADS:
        score += 3
    if first in profile_config.modifier_terms or first in GEO_HINTS:
        score += 2
    if first in GOOD_SUFFIXES and last in profile_config.modifier_terms:
        score -= 4
    if first in profile_config.head_terms and last in profile_config.modifier_terms:
        score -= 3
    if len(tokens) >= 2 and tokens[0] == tokens[1]:
        score = 1
    if len(tokens) == 2 and first in {"flow", "forge", "stream", "tools"} and last in {"pay", "prompt", "data", "ai"}:
        score -= 2
    if profile == "geo_local":
        if first in GEO_HINTS and last in profile_config.local_terms:
            score += 2
        elif last in GEO_HINTS:
            score -= 2
    if profile == "seo_exact":
        if last in profile_config.exact_match_terms:
            score += 1
        if first in GOOD_SUFFIXES:
            score -= 2

    return max(0, min(score, 10))


def linguistic_quality_score(name: str, tokens: Sequence[str], profile: str) -> int:
    """Aggregate core linguistic characteristics into a 30-point subscore."""
    return length_score(name) + pronounceability_score(name, tokens) + word_order_score(tokens, profile)


def brandability_score(name: str, tokens: Sequence[str], profile: str) -> int:
    """Measure memorability, clarity, and startup-style naming quality."""
    profile_config = get_profile(profile)
    score = 12

    if 5 <= len(name) <= 10:
        score += 4
    elif len(name) > 14:
        score -= 4

    if len(tokens) == 1:
        score += 3
    elif len(tokens) == 2:
        score += 4
    elif len(tokens) >= 3:
        score -= 3

    if tokens and tokens[-1] in GOOD_SUFFIXES:
        score += 3
    if name.startswith(tuple(BAD_PREFIXES)):
        score -= 4
    if len(set(tokens)) != len(tokens):
        score -= 3
    if any(token in profile_config.favored_terms for token in tokens):
        score += 2
    if profile in {"geo_local", "seo_exact"} and len(tokens) == 2:
        score += 1
    if profile == "seo_exact" and any(token in GOOD_SUFFIXES for token in tokens):
        score -= 2

    return max(0, min(score, 25))


def market_fit_score(tokens: Sequence[str], niche: str, profile: str) -> int:
    """Score alignment with the selected buyer intent profile."""
    profile_config = get_profile(profile)
    token_set = set(tokens)
    niche_terms = NICHE_HINTS.get(niche, set())
    score = 6

    if token_set & niche_terms:
        score += 4
    if token_set & profile_config.favored_terms:
        score += 5
    if profile == "ai_brand" and token_set & {"ai", "agent", "prompt", "model", "data", "bot"}:
        score += 4
    if profile == "startup_brand" and len(tokens) in {1, 2}:
        score += 2
    if profile == "flip_fast" and len(tokens) <= 2 and len("".join(tokens)) <= 10:
        score += 3
    if profile == "geo_local" and (token_set & GEO_HINTS) and (token_set & profile_config.local_terms):
        score += 6
    if profile == "seo_exact" and len(tokens) >= 2 and (token_set & profile_config.exact_match_terms):
        score += 5
    if profile == "seo_exact" and len(tokens) == 1:
        score -= 3
    if profile == "geo_local" and not (token_set & GEO_HINTS):
        score -= 3

    return max(0, min(score, 20))


def extension_fit_score(domain: str, tld: str, profile: str, tokens: Sequence[str]) -> int:
    """Score how appropriate the TLD is for the domain concept and buyer type."""
    _ = domain
    profile_config = get_profile(profile)
    token_set = set(tokens)

    if tld in profile_config.preferred_tlds:
        score = profile_config.preferred_tlds[tld]
    elif tld in profile_config.acceptable_tlds:
        score = profile_config.acceptable_tlds[tld]
    else:
        score = 2

    if profile == "ai_brand" and tld == ".ai" and token_set & {"ai", "agent", "prompt", "model", "data", "bot"}:
        score += 1
    if profile == "geo_local" and tld == ".com":
        score += 1
    if profile == "seo_exact" and tld == ".com" and token_set & profile_config.exact_match_terms:
        score += 1
    if tld in profile_config.discouraged_tlds:
        score -= 1

    return max(0, min(score, 10))


def liquidity_score(name: str, tokens: Sequence[str], tld: str, profile: str) -> int:
    """Estimate resale liquidity and buyer-pool breadth."""
    score = 2

    if tld == ".com":
        score += 3
    elif tld in {".ai", ".io", ".co"}:
        score += 1

    if len(name) <= 10:
        score += 2
    if len(tokens) in {1, 2}:
        score += 2
    if not (set(tokens) & GEO_HINTS) and profile != "geo_local":
        score += 1
    if set(tokens) & {"pay", "data", "cloud", "health", "fund", "trade", "care", "tools"}:
        score += 2
    if profile in {"geo_local", "seo_exact"}:
        score -= 1

    return max(0, min(score, 10))


def bonus_penalty_score(name: str, tokens: Sequence[str], hard_filter_penalty: int) -> int:
    """Apply controlled bonus and penalty adjustments."""
    score = hard_filter_penalty

    if len(tokens) == 2 and tokens[-1] in GOOD_SUFFIXES:
        score += 2
    if 5 <= len(name) <= 8:
        score += 1
    if any(token in {"ai", "data", "pay", "health", "care", "cloud"} for token in tokens):
        score += 1
    if name.startswith(tuple(BAD_PREFIXES)):
        score -= 2
    if len(tokens) >= 3:
        score -= 2

    return max(-15, min(score, 5))


def grade_from_score(score: int, rejected: bool) -> str:
    """Map the final score to a grade band."""
    if rejected or score <= 0:
        return "Reject"
    if score >= 93:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 68:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def resale_tier_from_grade(grade: str) -> tuple[str, str]:
    """Map grades to portfolio-friendly tier labels and rough value ranges."""
    if grade == "A+":
        return "Top Tier", "$5,000 - $25,000"
    if grade == "A":
        return "Top Tier", "$2,500 - $8,000"
    if grade == "B":
        return "Strong", "$800 - $2,500"
    if grade == "C":
        return "Speculative", "$250 - $800"
    if grade == "D":
        return "Weak", "$0 - $250"
    return "Reject", "$0"


def collect_flags(tokens: Sequence[str], profile: str, subscores: Mapping[str, int], tld: str) -> list[str]:
    """Derive user-facing positive flags from strong subscores and structure."""
    flags: list[str] = []
    token_set = set(tokens)

    if subscores["linguistic_quality"] >= 24:
        flags.extend(["smooth_pronunciation", "natural_word_order"])
    if subscores["brandability"] >= 18:
        flags.append("clean_structure")
    if subscores["extension_fit"] >= 8:
        flags.append("strong_extension_fit")
    if subscores["liquidity"] >= 8:
        flags.append("strong_liquidity")
    if len("".join(tokens)) <= 9:
        flags.append("compact_length")
    if profile == "ai_brand" and token_set & {"ai", "agent", "prompt", "model", "data", "bot"}:
        flags.append("strong_ai_fit")
    if profile == "startup_brand" and subscores["market_fit"] >= 14:
        flags.append("strong_startup_fit")
    if profile == "geo_local" and token_set & GEO_HINTS:
        flags.append("strong_local_fit")
    if profile == "seo_exact" and token_set & {"tools", "software", "repair", "clinic", "legal", "tax"}:
        flags.append("strong_exact_match_fit")
    if tld == ".ai" and profile == "ai_brand":
        flags.append("strong_ai_fit")

    return list(dict.fromkeys(flags))


def evaluate_domain(
    domain: str,
    profile: str = "startup_brand",
    niche: str = "",
    word_banks: Mapping[str, Sequence[str]] | None = None,
) -> DomainAppraisal:
    """Evaluate a full domain using the modular resale scoring engine."""
    name, tld = split_domain(domain)
    tokens = tokenize_name(name, word_banks, profile)
    hard_filter = apply_hard_filters(domain, name, tld, tokens, profile)

    if hard_filter.reject:
        subscores = {
            "linguistic_quality": 0,
            "brandability": 0,
            "market_fit": 0,
            "extension_fit": 0,
            "liquidity": 0,
            "bonus_penalty": hard_filter.penalty,
        }
        grade = grade_from_score(0, rejected=True)
        tier, value = resale_tier_from_grade(grade)
        explanation = build_explanation(domain, 0, hard_filter.flags, hard_filter.warnings, subscores)
        return DomainAppraisal(
            domain=domain,
            name=name,
            tld=tld,
            profile=profile,
            final_score=0,
            grade=grade,
            tier=tier,
            value=value,
            subscores=subscores,
            flags=list(hard_filter.flags),
            warnings=list(hard_filter.warnings),
            explanation=explanation,
            rejected=True,
        )

    subscores = {
        "linguistic_quality": linguistic_quality_score(name, tokens, profile),
        "brandability": brandability_score(name, tokens, profile),
        "market_fit": market_fit_score(tokens, niche, profile),
        "extension_fit": extension_fit_score(domain, tld, profile, tokens),
        "liquidity": liquidity_score(name, tokens, tld, profile),
        "bonus_penalty": bonus_penalty_score(name, tokens, hard_filter.penalty),
    }

    raw_score = sum(subscores.values())
    score_cap = hard_filter.score_cap

    pronunciation = pronounceability_score(name, tokens)
    order = word_order_score(tokens, profile)
    if pronunciation <= 4:
        score_cap = min(score_cap, 45) if score_cap is not None else 45
        hard_filter = hard_filter.__class__(
            reject=hard_filter.reject,
            score_cap=score_cap,
            penalty=hard_filter.penalty,
            flags=hard_filter.flags + ("poor_pronounceability",),
            warnings=hard_filter.warnings + ("pronunciation is very difficult",),
        )
    elif pronunciation <= 7:
        score_cap = min(score_cap, 58) if score_cap is not None else 58

    if order <= 3:
        score_cap = min(score_cap, 64) if score_cap is not None else 64
        if "awkward_word_order" not in hard_filter.flags:
            hard_filter = hard_filter.__class__(
                reject=hard_filter.reject,
                score_cap=score_cap,
                penalty=hard_filter.penalty,
                flags=hard_filter.flags + ("awkward_word_order",),
                warnings=hard_filter.warnings + ("word order feels unnatural",),
            )

    if subscores["extension_fit"] <= 3:
        score_cap = min(score_cap, 70) if score_cap is not None else 70

    final_score = raw_score
    if score_cap is not None:
        final_score = min(final_score, score_cap)
    final_score = max(0, min(final_score, 100))

    rejected = final_score < 35 or pronunciation <= 2
    grade = grade_from_score(final_score, rejected=rejected)
    tier, value = resale_tier_from_grade(grade)
    flags = collect_flags(tokens, profile, subscores, tld)
    all_flags = list(dict.fromkeys(list(hard_filter.flags) + flags))
    all_warnings = list(dict.fromkeys(hard_filter.warnings))
    explanation = build_explanation(domain, final_score, all_flags, all_warnings, subscores)

    return DomainAppraisal(
        domain=domain,
        name=name,
        tld=tld,
        profile=profile,
        final_score=final_score,
        grade=grade,
        tier=tier,
        value=value,
        subscores=subscores,
        flags=all_flags,
        warnings=all_warnings,
        explanation=explanation,
        rejected=rejected,
    )


def evaluate_domains(
    domains: Iterable[str],
    profile: str = "startup_brand",
    niche: str = "",
    word_banks: Mapping[str, Sequence[str]] | None = None,
) -> list[DomainAppraisal]:
    """Evaluate a list of full domains."""
    return [evaluate_domain(domain, profile=profile, niche=niche, word_banks=word_banks) for domain in domains]
