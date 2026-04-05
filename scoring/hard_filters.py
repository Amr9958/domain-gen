"""Hard filters and score caps for low-quality or risky domains."""

from __future__ import annotations

import re
from typing import Sequence

from scoring.interfaces import HardFilterResult


TRADEMARK_TERMS = {
    "google", "openai", "chatgpt", "microsoft", "apple", "amazon", "meta", "tesla", "nvidia",
    "paypal", "stripe", "uber", "tiktok", "netflix", "anthropic", "claude", "midjourney",
}

SPAM_TERMS = {
    "cheap", "free", "bonus", "winner", "casino", "bet", "loan", "debt", "profit", "crypto",
    "deal", "online", "best", "sale", "offer", "viral",
}

HARSH_ENDINGS = ("qx", "qz", "zx", "jq", "vj", "vf", "qj")


def _has_repeated_segment(name: str) -> bool:
    for size in range(2, 5):
        for index in range(len(name) - (size * 2) + 1):
            segment = name[index:index + size]
            if segment and segment == name[index + size:index + (size * 2)]:
                return True
    return False


def _has_ugly_join(name: str, tokens: Sequence[str]) -> bool:
    if len(tokens) < 2:
        return False
    for left, right in zip(tokens, tokens[1:]):
        if len(left) >= 2 and len(right) >= 2 and left[-2:] == right[:2]:
            return True
        if left[-1] == right[0] and left[-1] not in "aeiou":
            return True
    return False


def apply_hard_filters(domain: str, name: str, tld: str, tokens: Sequence[str], profile: str) -> HardFilterResult:
    """Apply non-negotiable quality checks before soft scoring."""
    flags: list[str] = []
    warnings: list[str] = []
    cap: int | None = None
    penalty = 0

    if len(name) < 4:
        return HardFilterResult(reject=True, flags=("too_short",), warnings=("too short for serious resale",))

    if len(name) > 20:
        return HardFilterResult(reject=True, flags=("too_long",), warnings=("excessive length hurts resale",))
    if len(name) > 16:
        flags.append("long_name")
        warnings.append("length reduces buyer pool")
        cap = 62
        penalty -= 5

    if any(char.isdigit() for char in name):
        flags.append("contains_numbers")
        warnings.append("numbers usually reduce trust and liquidity")
        cap = min(cap, 68) if cap is not None else 68
        penalty -= 8

    if "-" in domain:
        flags.append("contains_hyphen")
        warnings.append("hyphens rarely clear premium resale thresholds")
        cap = min(cap, 66) if cap is not None else 66
        penalty -= 8

    if _has_repeated_segment(name):
        flags.append("repeated_segment")
        warnings.append("repeated segment creates noisy branding")
        cap = min(cap, 58) if cap is not None else 58
        penalty -= 7

    if _has_ugly_join(name, tokens):
        flags.append("ugly_join")
        warnings.append("join between terms sounds unnatural")
        cap = min(cap, 63) if cap is not None else 63
        penalty -= 5

    if len(set(name)) <= max(3, len(name) // 4):
        flags.append("low_letter_variety")
        warnings.append("limited letter variety hurts memorability")
        cap = min(cap, 60) if cap is not None else 60
        penalty -= 5

    if any(term in name for term in SPAM_TERMS):
        flags.append("spam_pattern")
        warnings.append("contains low-trust commercial wording")
        cap = min(cap, 54) if cap is not None else 54
        penalty -= 10

    if name.endswith(HARSH_ENDINGS):
        flags.append("harsh_ending")
        warnings.append("awkward ending weakens pronunciation")
        cap = min(cap, 60) if cap is not None else 60
        penalty -= 4

    if profile in {"geo_local", "seo_exact"} and tld in {".ai", ".io", ".dev"}:
        flags.append("tld_profile_mismatch")
        warnings.append("extension is weak for local or exact-match buyers")
        cap = min(cap, 64) if cap is not None else 64
        penalty -= 4

    if any(term in name for term in TRADEMARK_TERMS):
        warnings.append("possible trademark overlap heuristic; not legal advice")
        flags.append("trademark_caution")
        penalty -= 6

    if re.search(r"[^a-z0-9.-]", domain):
        return HardFilterResult(reject=True, flags=("invalid_characters",), warnings=("contains invalid characters",))

    return HardFilterResult(
        reject=False,
        score_cap=cap,
        penalty=penalty,
        flags=tuple(dict.fromkeys(flags)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
