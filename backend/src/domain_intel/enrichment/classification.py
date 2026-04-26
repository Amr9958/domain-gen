"""Rule-based starter classification hints for domain enrichment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Iterable, List

from domain_intel.core.enums import DomainType, StarterDomainLabel
from domain_intel.enrichment.contracts import DomainClassificationHint, DomainTarget, StarterLabelMatch


GEO_TOKENS = {
    "atlanta",
    "austin",
    "boston",
    "brooklyn",
    "cairo",
    "california",
    "chicago",
    "dallas",
    "denver",
    "dubai",
    "houston",
    "la",
    "london",
    "miami",
    "ny",
    "nyc",
    "orlando",
    "phoenix",
    "texas",
    "toronto",
}

SERVICE_TOKENS = {
    "attorney",
    "cleaning",
    "clinic",
    "contractor",
    "dentist",
    "electric",
    "electrician",
    "garage",
    "hvac",
    "lawyer",
    "locksmith",
    "movers",
    "painter",
    "painting",
    "pest",
    "plumber",
    "plumbing",
    "repair",
    "restoration",
    "roofing",
    "solar",
    "tree",
    "towing",
}

TECH_TOKENS = {
    "agent",
    "ai",
    "api",
    "app",
    "automation",
    "bot",
    "cloud",
    "code",
    "compute",
    "cyber",
    "data",
    "dev",
    "infra",
    "model",
    "robot",
    "saas",
    "signal",
    "software",
    "stack",
    "tech",
}

EXACT_MATCH_TOKENS = GEO_TOKENS | SERVICE_TOKENS | TECH_TOKENS | {
    "bank",
    "capital",
    "credit",
    "domain",
    "growth",
    "health",
    "home",
    "insurance",
    "legal",
    "repair",
    "travel",
}

DICTIONARY_PREMIUM_TOKENS = {
    "anchor",
    "atlas",
    "beacon",
    "cedar",
    "cloud",
    "forge",
    "harbor",
    "horizon",
    "logic",
    "mint",
    "orbit",
    "prime",
    "river",
    "signal",
    "summit",
    "vector",
}

BRANDABLE_FRIENDLY_TOKENS = DICTIONARY_PREMIUM_TOKENS | {
    "aero",
    "arc",
    "nova",
    "pixel",
    "pulse",
    "spark",
    "terra",
    "vertex",
}

MODIFIER_TOKENS = {
    "best",
    "go",
    "group",
    "hq",
    "hub",
    "labs",
    "local",
    "my",
    "now",
    "online",
    "pro",
    "pros",
}


@dataclass(frozen=True)
class StarterDomainClassificationEngine:
    """Explainable starter rule engine for enrichment-stage classification hints."""

    algorithm_version: str = "starter-classifier-v1"

    def classify(self, target: DomainTarget) -> DomainClassificationHint:
        """Return explainable starter labels derived from domain text only."""

        normalized_sld = target.sld.lower()
        tokens = _tokenize_sld(normalized_sld)
        unmatched_tokens = [token for token in tokens if token not in _LEXICON]

        matched_geo = [token for token in tokens if token in GEO_TOKENS]
        matched_services = [token for token in tokens if token in SERVICE_TOKENS]
        matched_tech = [token for token in tokens if token in TECH_TOKENS]
        matched_dictionary = [token for token in tokens if token in DICTIONARY_PREMIUM_TOKENS]

        labels: List[StarterLabelMatch] = []
        alpha_only = bool(re.fullmatch(r"[a-z-]+", normalized_sld))
        has_digits = any(character.isdigit() for character in normalized_sld)
        compact_length = len(normalized_sld.replace("-", ""))

        if matched_geo and matched_services:
            labels.append(
                _label(
                    StarterDomainLabel.GEO_SERVICE,
                    "0.9600",
                    f"Matched geo token(s) {matched_geo} and service token(s) {matched_services}.",
                    matched_geo + matched_services,
                    DomainType.GEO,
                )
            )
            labels.append(
                _label(
                    StarterDomainLabel.LOCAL_LEAD_GEN,
                    "0.9300",
                    "Geo + service construction is a common local lead-gen pattern.",
                    matched_geo + matched_services,
                    DomainType.KEYWORD_PHRASE,
                )
            )
        elif matched_services and ("local" in tokens or "pros" in tokens or "pro" in tokens):
            labels.append(
                _label(
                    StarterDomainLabel.LOCAL_LEAD_GEN,
                    "0.8100",
                    "Matched a local-service token with a service modifier such as 'local' or 'pros'.",
                    matched_services,
                    DomainType.KEYWORD_PHRASE,
                )
            )

        if matched_tech:
            mapped_type = DomainType.EXACT_MATCH if not unmatched_tokens else DomainType.KEYWORD_PHRASE
            labels.append(
                _label(
                    StarterDomainLabel.AI_TECH,
                    "0.8400" if "ai" in matched_tech else "0.7700",
                    f"Matched technology token(s) {matched_tech}.",
                    matched_tech,
                    mapped_type,
                )
            )

        if compact_length <= 5 and alpha_only and not has_digits:
            labels.append(
                _label(
                    StarterDomainLabel.SHORT_DOMAIN,
                    "0.9200" if compact_length <= 4 else "0.8600",
                    f"Second-level domain length is {compact_length}, which qualifies as a short domain.",
                    [normalized_sld.replace("-", "")],
                    None,
                )
            )

        if (
            len(tokens) == 1
            and tokens[0] in DICTIONARY_PREMIUM_TOKENS
            and target.tld.lower() == "com"
            and alpha_only
            and not has_digits
        ):
            labels.append(
                _label(
                    StarterDomainLabel.DICTIONARY_PREMIUM,
                    "0.9400",
                    "Single clean .com token matched the curated premium dictionary set.",
                    matched_dictionary or tokens,
                    DomainType.PREMIUM_GENERIC,
                )
            )

        recognized_exact = [token for token in tokens if token in EXACT_MATCH_TOKENS]
        if recognized_exact and len(recognized_exact) == len(tokens) and not has_digits:
            mapped_type = DomainType.GEO if matched_geo and matched_services else DomainType.EXACT_MATCH
            labels.append(
                _label(
                    StarterDomainLabel.EXACT_MATCH,
                    "0.9100" if len(tokens) > 1 else "0.7900",
                    "All tokens matched the deterministic keyword lexicon with no unresolved fragments.",
                    tokens,
                    mapped_type,
                )
            )
        elif recognized_exact and unmatched_tokens:
            labels.append(
                _label(
                    StarterDomainLabel.PARTIAL_MATCH,
                    "0.7300",
                    "Domain mixes recognized commercial tokens with unresolved brand or modifier fragments.",
                    recognized_exact,
                    DomainType.KEYWORD_PHRASE,
                )
            )

        pronounceable = _is_pronounceable(normalized_sld.replace("-", ""))
        if alpha_only and not has_digits and 5 <= compact_length <= 12 and pronounceable:
            if not recognized_exact and not matched_dictionary and len(tokens) == 1:
                labels.append(
                    _label(
                        StarterDomainLabel.MADE_UP_BRAND,
                        "0.8300",
                        "Single-token domain looks pronounceable but did not match the deterministic dictionary sets.",
                        tokens,
                        DomainType.BRANDABLE,
                    )
                )
            if (
                len(tokens) == 1
                and tokens[0] not in DICTIONARY_PREMIUM_TOKENS
                and (tokens[0] in BRANDABLE_FRIENDLY_TOKENS or tokens[0] in unmatched_tokens or pronounceable)
            ):
                labels.append(
                    _label(
                        StarterDomainLabel.BRANDABLE,
                        "0.7600",
                        "Pronounceable single-token domain passes the starter brandability heuristics.",
                        tokens,
                        DomainType.BRANDABLE,
                    )
                )

        labels = _dedupe_and_sort(labels)
        primary_label = labels[0].label if labels else None
        mapped_domain_type = labels[0].mapped_domain_type if labels else None
        business_category = _infer_business_category(matched_services=matched_services, matched_tech=matched_tech)
        return DomainClassificationHint(
            primary_label=primary_label,
            mapped_domain_type=mapped_domain_type,
            business_category=business_category,
            labels=labels,
            tokens=tokens,
            unmatched_tokens=unmatched_tokens,
        )


def _label(
    label: StarterDomainLabel,
    confidence_score: str,
    reason: str,
    matched_tokens: List[str],
    mapped_domain_type: DomainType | None,
) -> StarterLabelMatch:
    return StarterLabelMatch(
        label=label,
        confidence_score=Decimal(confidence_score),
        reason=reason,
        matched_tokens=matched_tokens,
        mapped_domain_type=mapped_domain_type,
    )


def _dedupe_and_sort(labels: Iterable[StarterLabelMatch]) -> List[StarterLabelMatch]:
    best_by_label: dict[StarterDomainLabel, StarterLabelMatch] = {}
    for label in labels:
        current = best_by_label.get(label.label)
        if current is None or label.confidence_score > current.confidence_score:
            best_by_label[label.label] = label
    ordered = list(best_by_label.values())
    ordered.sort(key=lambda item: (item.confidence_score, _label_priority(item.label)), reverse=True)
    return ordered


def _label_priority(label: StarterDomainLabel) -> int:
    priorities = {
        StarterDomainLabel.GEO_SERVICE: 9,
        StarterDomainLabel.LOCAL_LEAD_GEN: 8,
        StarterDomainLabel.DICTIONARY_PREMIUM: 7,
        StarterDomainLabel.EXACT_MATCH: 6,
        StarterDomainLabel.AI_TECH: 5,
        StarterDomainLabel.MADE_UP_BRAND: 4,
        StarterDomainLabel.BRANDABLE: 3,
        StarterDomainLabel.PARTIAL_MATCH: 2,
        StarterDomainLabel.SHORT_DOMAIN: 1,
    }
    return priorities[label]


def _infer_business_category(*, matched_services: List[str], matched_tech: List[str]) -> str | None:
    if matched_services:
        return "local_services"
    if matched_tech:
        return "technology"
    return None


@lru_cache(maxsize=2048)
def _tokenize_sld(sld: str) -> List[str]:
    clean = re.sub(r"[^a-z0-9-]", "", sld.lower())
    if not clean:
        return []
    if "-" in clean:
        return [token for token in clean.split("-") if token]

    tokens: List[str] = []
    index = 0
    while index < len(clean):
        token = _longest_prefix_match(clean[index:])
        if token is not None:
            tokens.append(token)
            index += len(token)
            continue

        next_index = index + 1
        while next_index < len(clean) and _longest_prefix_match(clean[next_index:]) is None:
            next_index += 1
        tokens.append(clean[index:next_index])
        index = next_index
    return tokens


@lru_cache(maxsize=4096)
def _longest_prefix_match(fragment: str) -> str | None:
    for token in _LEXICON_BY_LENGTH:
        if fragment.startswith(token):
            return token
    return None


def _is_pronounceable(token: str) -> bool:
    if len(token) < 4 or not token.isalpha():
        return False
    vowels = sum(1 for character in token if character in {"a", "e", "i", "o", "u", "y"})
    consonant_runs = max((len(match.group(0)) for match in re.finditer(r"[^aeiouy]+", token)), default=0)
    return vowels >= 2 and consonant_runs <= 4


_LEXICON = EXACT_MATCH_TOKENS | DICTIONARY_PREMIUM_TOKENS | BRANDABLE_FRIENDLY_TOKENS | MODIFIER_TOKENS
_LEXICON_BY_LENGTH = tuple(sorted(_LEXICON, key=len, reverse=True))
