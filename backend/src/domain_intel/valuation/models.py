"""Typed request and response models for deterministic domain valuation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple
from uuid import UUID

from domain_intel.core.enums import (
    ConfidenceLevel,
    DomainType,
    ReasonDirection,
    ValuationRefusalCode,
    ValuationStatus,
    ValueTier,
)


class ScoreDimension(str, Enum):
    """Supported valuation score dimensions."""

    PRONUNCIATION = "pronunciation"
    MEMORABILITY = "memorability"
    CLARITY = "clarity"
    BREVITY = "brevity"
    SEMANTIC_COHERENCE = "semantic_coherence"
    BRANDABILITY = "brandability"
    COMMERCIAL_DEMAND = "commercial_demand"
    TLD_ECOSYSTEM_STRENGTH = "tld_ecosystem_strength"
    UPGRADE_TARGET_STRENGTH = "upgrade_target_strength"
    HISTORICAL_LEGITIMACY = "historical_legitimacy"
    ACTIVE_BUSINESS_RELEVANCE = "active_business_relevance"
    COMPARABLE_SALES_SUPPORT = "comparable_sales_support"
    TREND_RELEVANCE = "trend_relevance"
    LIQUIDITY = "liquidity"


class InvestmentRecommendation(str, Enum):
    """High-level investor workflow recommendation."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    PASS = "pass"


@dataclass(frozen=True)
class EvidenceRef:
    """Stable traceability reference for facts, signals, or external inputs."""

    type: str
    id: str
    source: str
    observed_at: Optional[datetime] = None


@dataclass(frozen=True)
class DomainRecord:
    """Canonical domain identity needed by the valuation engine."""

    id: UUID
    fqdn: str
    sld: str
    tld: str
    is_valid: bool = True


@dataclass(frozen=True)
class ClassificationSnapshot:
    """Stored classification input required before pricing."""

    classification_result_id: UUID
    domain_type: DomainType
    confidence_score: float
    business_category: Optional[str] = None
    language_code: Optional[str] = None
    tokens: Tuple[str, ...] = field(default_factory=tuple)
    risk_flags: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HistoricalSignals:
    """Verified historical evidence and legitimacy signals."""

    years_since_first_seen: Optional[float] = None
    active_website_years: Optional[float] = None
    archive_snapshot_count: Optional[int] = None
    website_resolves: Optional[bool] = None
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)

    def has_data(self) -> bool:
        return any(
            value is not None
            for value in (
                self.years_since_first_seen,
                self.active_website_years,
                self.archive_snapshot_count,
                self.website_resolves,
            )
        )


@dataclass(frozen=True)
class MarketDemandSignals:
    """Derived commercial demand and relevance inputs."""

    commercial_intent_score: Optional[float] = None
    active_business_score: Optional[float] = None
    active_business_count: Optional[int] = None
    search_demand_score: Optional[float] = None
    trend_score: Optional[float] = None
    liquidity_score: Optional[float] = None
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)

    def has_data(self) -> bool:
        return any(
            value is not None
            for value in (
                self.commercial_intent_score,
                self.active_business_score,
                self.active_business_count,
                self.search_demand_score,
                self.trend_score,
                self.liquidity_score,
            )
        )


@dataclass(frozen=True)
class RiskSignals:
    """Risk inputs that can reduce confidence or block pricing."""

    trademark_risk_score: Optional[float] = None
    typo_confusion_score: Optional[float] = None
    adult_sensitivity_score: Optional[float] = None
    legal_notes: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComparableSale:
    """Verified comparable sale record supplied by a provider or manual import."""

    sale_id: str
    domain: str
    price: Decimal
    currency: str
    similarity_score: float
    sold_at: Optional[datetime] = None
    source_name: str = "manual"
    same_tld: bool = True
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComparableSalesSupport:
    """Comparable-sale support bundle for explainable pricing."""

    sales: Tuple[ComparableSale, ...] = field(default_factory=tuple)
    quality_score: Optional[float] = None
    notes: Tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)

    def has_data(self) -> bool:
        return bool(self.sales)


@dataclass(frozen=True)
class TldEcosystemSignals:
    """TLD and upgrade ecosystem strength inputs."""

    tld: str
    registry_strength_score: Optional[float] = None
    aftermarket_liquidity_score: Optional[float] = None
    end_user_adoption_score: Optional[float] = None
    upgrade_target_score: Optional[float] = None
    registered_extension_count: Optional[int] = None
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)

    def has_provider_data(self) -> bool:
        return any(
            value is not None
            for value in (
                self.registry_strength_score,
                self.aftermarket_liquidity_score,
                self.end_user_adoption_score,
                self.upgrade_target_score,
                self.registered_extension_count,
            )
        )


@dataclass(frozen=True)
class DomainValuationRequest:
    """Input bundle for classification-aware valuation."""

    domain: DomainRecord
    classification: Optional[ClassificationSnapshot]
    historical_signals: HistoricalSignals = field(default_factory=HistoricalSignals)
    market_signals: MarketDemandSignals = field(default_factory=MarketDemandSignals)
    risk_signals: RiskSignals = field(default_factory=RiskSignals)
    comparable_support: Optional[ComparableSalesSupport] = None
    ecosystem_signals: Optional[TldEcosystemSignals] = None
    facts_are_stale: bool = False
    has_conflicting_facts: bool = False
    currency: str = "USD"
    algorithm_version: str = "valuation-v1"
    input_fact_ids: Tuple[UUID, ...] = field(default_factory=tuple)
    input_signal_ids: Tuple[UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MoneyRange:
    """Money range value object."""

    min_amount: Decimal
    max_amount: Decimal
    currency: str

    @property
    def point_amount(self) -> Decimal:
        return (self.min_amount + self.max_amount) / Decimal("2")


@dataclass(frozen=True)
class MoneyPoint:
    """Single money recommendation point."""

    amount: Decimal
    currency: str


@dataclass(frozen=True)
class ScoreBreakdown:
    """Explainable score contribution for one dimension."""

    dimension: ScoreDimension
    weight: float
    score: float
    weighted_points: float
    explanation: str
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RiskPenalty:
    """Explainable risk penalty applied after positive scoring."""

    code: str
    label: str
    points: float
    explanation: str


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Human-readable confidence output."""

    level: ConfidenceLevel
    score: float
    rationale: str


@dataclass(frozen=True)
class ValuationReason:
    """Structured reasoning entry that can later map to persisted reason codes."""

    code: str
    label: str
    direction: ReasonDirection
    impact_weight: float
    explanation: str
    impact_amount: Optional[Decimal] = None
    evidence_refs: Tuple[EvidenceRef, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValuationResult:
    """Deterministic valuation output or refusal state."""

    status: ValuationStatus
    score: Optional[int]
    grade: Optional[str]
    confidence: ConfidenceAssessment
    value_tier: ValueTier
    domain_type: Optional[DomainType]
    estimated_value_min: Optional[Decimal]
    estimated_value_max: Optional[Decimal]
    estimated_value_point: Optional[Decimal]
    wholesale_estimate: Optional[MoneyRange]
    retail_estimate: Optional[MoneyRange]
    bin_recommendation: Optional[MoneyPoint]
    minimum_acceptable_offer: Optional[MoneyPoint]
    hold_strategy: str
    investment_recommendation: InvestmentRecommendation
    pricing_basis: str
    score_breakdown: Tuple[ScoreBreakdown, ...]
    risk_penalties: Tuple[RiskPenalty, ...]
    reason_codes: Tuple[ValuationReason, ...]
    classification_result_id: Optional[UUID]
    refusal_code: Optional[ValuationRefusalCode] = None
    refusal_reason: Optional[str] = None
    remediation: Tuple[str, ...] = field(default_factory=tuple)
    input_fact_ids: Tuple[UUID, ...] = field(default_factory=tuple)
    input_signal_ids: Tuple[UUID, ...] = field(default_factory=tuple)
    algorithm_version: str = "valuation-v1"
