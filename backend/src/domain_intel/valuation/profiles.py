"""Classification-aware score weight profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from domain_intel.core.enums import DomainType
from domain_intel.valuation.models import ScoreDimension


BASE_SCORE_WEIGHTS: Dict[ScoreDimension, float] = {
    ScoreDimension.PRONUNCIATION: 8.0,
    ScoreDimension.MEMORABILITY: 8.0,
    ScoreDimension.CLARITY: 7.0,
    ScoreDimension.BREVITY: 8.0,
    ScoreDimension.SEMANTIC_COHERENCE: 8.0,
    ScoreDimension.BRANDABILITY: 9.0,
    ScoreDimension.COMMERCIAL_DEMAND: 14.0,
    ScoreDimension.TLD_ECOSYSTEM_STRENGTH: 7.0,
    ScoreDimension.UPGRADE_TARGET_STRENGTH: 6.0,
    ScoreDimension.HISTORICAL_LEGITIMACY: 5.0,
    ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 6.0,
    ScoreDimension.COMPARABLE_SALES_SUPPORT: 7.0,
    ScoreDimension.TREND_RELEVANCE: 3.0,
    ScoreDimension.LIQUIDITY: 4.0,
}


PROFILE_MULTIPLIERS: Dict[DomainType, Dict[ScoreDimension, float]] = {
    DomainType.EXACT_MATCH: {
        ScoreDimension.SEMANTIC_COHERENCE: 1.20,
        ScoreDimension.COMMERCIAL_DEMAND: 1.20,
        ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 1.15,
        ScoreDimension.COMPARABLE_SALES_SUPPORT: 1.10,
        ScoreDimension.BRANDABILITY: 0.85,
        ScoreDimension.TREND_RELEVANCE: 0.85,
    },
    DomainType.PREMIUM_GENERIC: {
        ScoreDimension.MEMORABILITY: 1.10,
        ScoreDimension.SEMANTIC_COHERENCE: 1.15,
        ScoreDimension.COMMERCIAL_DEMAND: 1.15,
        ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 1.10,
        ScoreDimension.COMPARABLE_SALES_SUPPORT: 1.10,
        ScoreDimension.TREND_RELEVANCE: 0.90,
    },
    DomainType.GEO: {
        ScoreDimension.CLARITY: 1.10,
        ScoreDimension.SEMANTIC_COHERENCE: 1.10,
        ScoreDimension.COMMERCIAL_DEMAND: 1.15,
        ScoreDimension.UPGRADE_TARGET_STRENGTH: 1.10,
        ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 1.15,
        ScoreDimension.BRANDABILITY: 0.85,
    },
    DomainType.KEYWORD_PHRASE: {
        ScoreDimension.CLARITY: 1.10,
        ScoreDimension.SEMANTIC_COHERENCE: 1.15,
        ScoreDimension.COMMERCIAL_DEMAND: 1.10,
        ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 1.05,
        ScoreDimension.BRANDABILITY: 0.80,
        ScoreDimension.BREVITY: 0.90,
    },
    DomainType.BRANDABLE: {
        ScoreDimension.PRONUNCIATION: 1.15,
        ScoreDimension.MEMORABILITY: 1.15,
        ScoreDimension.BREVITY: 1.10,
        ScoreDimension.BRANDABILITY: 1.25,
        ScoreDimension.LIQUIDITY: 1.10,
        ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 0.80,
        ScoreDimension.COMPARABLE_SALES_SUPPORT: 0.90,
    },
    DomainType.ACRONYM: {
        ScoreDimension.BREVITY: 1.25,
        ScoreDimension.LIQUIDITY: 1.15,
        ScoreDimension.COMPARABLE_SALES_SUPPORT: 1.10,
        ScoreDimension.PRONUNCIATION: 0.70,
        ScoreDimension.CLARITY: 0.80,
        ScoreDimension.BRANDABILITY: 0.85,
    },
    DomainType.NUMERIC: {
        ScoreDimension.BREVITY: 1.15,
        ScoreDimension.LIQUIDITY: 1.05,
        ScoreDimension.COMPARABLE_SALES_SUPPORT: 1.05,
        ScoreDimension.PRONUNCIATION: 0.50,
        ScoreDimension.CLARITY: 0.65,
        ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: 0.75,
    },
    DomainType.PERSONAL_NAME: {
        ScoreDimension.PRONUNCIATION: 1.05,
        ScoreDimension.MEMORABILITY: 1.05,
        ScoreDimension.SEMANTIC_COHERENCE: 0.95,
        ScoreDimension.COMMERCIAL_DEMAND: 0.80,
        ScoreDimension.COMPARABLE_SALES_SUPPORT: 0.85,
        ScoreDimension.LIQUIDITY: 0.80,
    },
}


@dataclass(frozen=True)
class WeightProfile:
    """Resolved per-domain-type score weight profile."""

    domain_type: DomainType
    weights: Mapping[ScoreDimension, float]


def resolve_weight_profile(domain_type: DomainType) -> WeightProfile:
    """Return normalized weights summing to 100 for the given domain type."""

    multipliers = PROFILE_MULTIPLIERS.get(domain_type, {})
    adjusted = {
        dimension: weight * multipliers.get(dimension, 1.0)
        for dimension, weight in BASE_SCORE_WEIGHTS.items()
    }
    total = sum(adjusted.values()) or 1.0
    normalized = {
        dimension: (weight / total) * 100.0
        for dimension, weight in adjusted.items()
    }
    return WeightProfile(domain_type=domain_type, weights=normalized)
