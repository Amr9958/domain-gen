"""Domain generation helpers."""

from __future__ import annotations

import random
import re
from typing import Mapping, Sequence

from providers.llm import llm_creative_boost


VOWELS = "aeiou"
INVENT_PREFIXES = (
    "zy", "ter", "vel", "nov", "lum", "syn", "kor", "nex", "sol", "ver", "aer", "zen",
)
INVENT_SUFFIXES = (
    "ta", "ra", "za", "sa", "va", "lo", "ro", "sy", "us", "ix", "a", "o",
)


def _clean_name(name: str) -> str:
    """Normalize raw text into a compact lower-case candidate."""
    return re.sub(r"[^a-z]", "", name.lower())


def _is_valid_candidate(name: str) -> bool:
    """Keep candidates within a resale-friendly character window."""
    return 4 <= len(name) <= 18


def _candidate_record(name: str, method: str, source_name: str = "") -> dict[str, str | bool]:
    """Build a metadata-rich candidate record for downstream comparison."""
    return {
        "name": name,
        "method": method,
        "source_name": source_name,
        "is_transformed": bool(source_name and source_name != name),
    }


def _append_candidate(
    candidates: dict[str, dict[str, str | bool]],
    raw_name: str,
    method: str,
    source_name: str = "",
) -> None:
    """Add a normalized candidate if it clears basic structural checks."""
    clean_name = _clean_name(raw_name)
    clean_source = _clean_name(source_name)
    if not _is_valid_candidate(clean_name):
        return
    if clean_name not in candidates:
        candidates[clean_name] = _candidate_record(clean_name, method, clean_source)


def _random_bank_word(word_banks: Mapping[str, Sequence[str]], excluded: set[str]) -> str:
    """Pick a random word from any non-excluded bank."""
    categories = [category for category in word_banks.keys() if category not in excluded and word_banks[category]]
    category = random.choice(categories)
    return random.choice(word_banks[category])


def _build_base_name(
    word_banks: Mapping[str, Sequence[str]],
    user_keywords: Sequence[str],
) -> tuple[str, str]:
    """Generate a seed candidate using combine-oriented rules."""
    word1 = _random_bank_word(word_banks, {"short_prefixes"})
    roll = random.random()

    if user_keywords and roll > 0.35:
        keyword = random.choice(user_keywords)
        if random.random() > 0.5:
            return keyword + word1, "combine"
        return word1 + keyword, "combine"

    if roll > 0.7 and word_banks.get("short_prefixes"):
        prefix = random.choice(word_banks["short_prefixes"])
        return prefix + word1, "combine"

    word2 = _random_bank_word(word_banks, {"short_prefixes"})
    return word1 + word2, "combine"


def _twist_name(name: str) -> str:
    """Create a phonetic brand twist from a base name."""
    if len(name) < 4:
        return ""
    if name.endswith("e") and len(name) >= 5:
        return name[:-1] + "a"
    if name.endswith(("er", "or")) and len(name) >= 6:
        return name[:-2] + "ra"
    if name[-1] not in VOWELS and len(name) <= 9:
        return name + random.choice(("a", "o", "i"))
    return name[:-1] + random.choice(("a", "o")) if len(name) >= 5 else ""


def _cut_name(name: str) -> str:
    """Shorten a name while trying to preserve readability."""
    if len(name) <= 5:
        return ""
    if name.endswith(("al", "el", "er", "or", "um")):
        return name[:-1]
    if name.endswith("ex") and len(name) >= 6:
        return name[:-1]
    if len(name) >= 7:
        return name[:-1]
    return ""


def _invent_name() -> str:
    """Build an invented but pronounceable brand-style candidate."""
    prefix = random.choice(INVENT_PREFIXES)
    suffix = random.choice(INVENT_SUFFIXES)
    middle = random.choice(("", "", random.choice(("n", "r", "s", "l"))))
    return prefix + middle + suffix


def generate_domains(
    niche: str,
    use_llm: bool,
    word_banks: Mapping[str, Sequence[str]],
    keywords_str: str = "",
    num_per_tier: int = 15,
) -> list[dict[str, str | bool]]:
    """Generate a pool of candidate base names plus transformed variants."""
    _ = niche
    user_keywords = [_clean_name(keyword.strip()) for keyword in keywords_str.split(",") if keyword.strip()]
    candidates: dict[str, dict[str, str | bool]] = {}
    base_names: list[str] = []
    loop_count = max(num_per_tier * 6, 24)

    for _ in range(loop_count):
        raw_name, method = _build_base_name(word_banks, user_keywords)
        clean_name = _clean_name(raw_name)
        if not _is_valid_candidate(clean_name):
            continue
        if clean_name not in candidates:
            candidates[clean_name] = _candidate_record(clean_name, method)
            base_names.append(clean_name)

    for base_name in list(base_names):
        _append_candidate(candidates, _twist_name(base_name), "twist", source_name=base_name)
        _append_candidate(candidates, _cut_name(base_name), "cut", source_name=base_name)

    invent_count = max(4, num_per_tier // 2)
    for _ in range(invent_count):
        _append_candidate(candidates, _invent_name(), "invent")

    if use_llm:
        llm_names = llm_creative_boost(niche, list(candidates.keys()), count=num_per_tier)
        for suggestion in llm_names:
            _append_candidate(candidates, suggestion, "invent")

    return list(candidates.values())
