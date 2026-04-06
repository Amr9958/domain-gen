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


def _normalize_keywords(keywords_str: str) -> list[str]:
    """Parse and deduplicate user-selected keywords."""
    ordered_keywords: list[str] = []
    seen: set[str] = set()
    for raw_keyword in keywords_str.split(","):
        clean_keyword = _clean_name(raw_keyword.strip())
        if len(clean_keyword) < 3 or clean_keyword in seen:
            continue
        seen.add(clean_keyword)
        ordered_keywords.append(clean_keyword)
    return ordered_keywords


def _merge_parts(left: str, right: str) -> str:
    """Join two strings while trimming obvious overlap at the boundary."""
    if not left:
        return right
    if not right:
        return left
    if left[-1] == right[0]:
        return left + right[1:]
    return left + right


def _keyword_front(word: str) -> str:
    """Take a reusable front chunk from a selected keyword."""
    if len(word) <= 5:
        return word
    return word[: max(3, min(6, (len(word) + 1) // 2))]


def _keyword_back(word: str) -> str:
    """Take a reusable back chunk from a selected keyword."""
    if len(word) <= 5:
        return word
    return word[-max(3, min(6, len(word) // 2)) :]


def _build_keyword_base_names(user_keywords: Sequence[str], target_count: int) -> list[tuple[str, str]]:
    """Generate keyword-anchored base names using only selected keywords and their fragments."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(raw_name: str, method: str) -> None:
        clean_name = _clean_name(raw_name)
        if not _is_valid_candidate(clean_name) or clean_name in seen:
            return
        seen.add(clean_name)
        results.append((clean_name, method))

    for keyword in user_keywords:
        add(keyword, "keyword")
        add(_cut_name(keyword), "cut")
        add(_twist_name(keyword), "twist")
        if len(results) >= target_count:
            return results

    for left in user_keywords:
        for right in user_keywords:
            if left == right:
                continue
            add(_merge_parts(left, right), "combine")
            add(_merge_parts(_keyword_front(left), right), "combine")
            add(_merge_parts(left, _keyword_back(right)), "combine")
            add(_merge_parts(_keyword_front(left), _keyword_back(right)), "blend")
            if len(results) >= target_count:
                return results

    return results


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
    user_keywords = _normalize_keywords(keywords_str)
    candidates: dict[str, dict[str, str | bool]] = {}
    base_names: list[str] = []
    target_candidate_count = max(num_per_tier * 8, len(user_keywords) * 10, 40)
    loop_count = max(num_per_tier * 10, 60)

    if user_keywords:
        for clean_name, method in _build_keyword_base_names(user_keywords, target_candidate_count):
            if clean_name not in candidates:
                candidates[clean_name] = _candidate_record(clean_name, method)
                base_names.append(clean_name)

    if not user_keywords:
        while len(candidates) < target_candidate_count and len(base_names) < target_candidate_count and loop_count > 0:
            loop_count -= 1
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

    if not user_keywords:
        invent_count = max(4, num_per_tier // 2)
        for _ in range(invent_count):
            _append_candidate(candidates, _invent_name(), "invent")

    if use_llm:
        llm_names = llm_creative_boost(
            niche,
            list(candidates.keys()),
            selected_keywords=user_keywords,
            count=max(num_per_tier, len(user_keywords)),
        )
        for suggestion in llm_names:
            _append_candidate(candidates, suggestion, "invent")

    return list(candidates.values())
