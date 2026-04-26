"""Stored appraisal report JSON contract."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MoneyContract(BaseModel):
    """Stable money contract used inside stored report JSON."""

    amount: str
    currency: str


class ValueRangeContract(BaseModel):
    """Stable min/max range contract."""

    low: str
    high: str
    currency: str


class EvidenceReferenceContract(BaseModel):
    """Reference to a verified fact, signal, reason code, or explanation."""

    kind: str
    ref_id: str
    label: Optional[str] = None


class DomainHeaderContract(BaseModel):
    """Header block for a domain appraisal report."""

    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: Optional[str] = None
    is_valid: bool
    auction_id: Optional[str] = None


class ClassificationContract(BaseModel):
    """Structured domain classification summary."""

    domain_type: Optional[str] = None
    business_category: Optional[str] = None
    language_code: Optional[str] = None
    confidence_score: Optional[float] = None
    risk_flags: List[dict] = Field(default_factory=list)
    refusal_reason: Optional[str] = None


class WhoisIntelligenceContract(BaseModel):
    """WHOIS/registration snapshot assembled from verified facts only."""

    status: str
    registrar: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status_labels: List[str] = Field(default_factory=list)
    nameservers: List[str] = Field(default_factory=list)
    privacy_protected: Optional[bool] = None
    registrant_country: Optional[str] = None
    source_fact_ids: List[str] = Field(default_factory=list)


class TLDEcosystemSummaryContract(BaseModel):
    """Extension ecosystem block for report reads and dashboard use."""

    status: str
    registered_extensions: List[str] = Field(default_factory=list)
    active_website_extensions: List[str] = Field(default_factory=list)
    parked_extensions: List[str] = Field(default_factory=list)
    extension_count: Optional[int] = None
    narrative_flags: List[str] = Field(default_factory=list)
    source_refs: List[EvidenceReferenceContract] = Field(default_factory=list)


class MarketAnalysisSummaryContract(BaseModel):
    """Deterministic market and auction snapshot."""

    auction_status: Optional[str] = None
    auction_type: Optional[str] = None
    marketplace_code: Optional[str] = None
    current_bid: Optional[MoneyContract] = None
    auction_end_at: Optional[datetime] = None
    bid_count: Optional[int] = None
    watchers_count: Optional[int] = None
    bid_to_estimated_wholesale_ratio: Optional[float] = None
    bid_to_estimated_retail_ratio: Optional[float] = None
    supporting_reasons: List[str] = Field(default_factory=list)
    limiting_reasons: List[str] = Field(default_factory=list)
    market_signals: List[str] = Field(default_factory=list)


class ScoreComponentContract(BaseModel):
    """Single score component for dashboard and report display."""

    code: str
    label: str
    score: Optional[float] = None
    direction: Optional[str] = None
    explanation: Optional[str] = None


class ScoreBreakdownContract(BaseModel):
    """Explainable score summary compiled from signals and reason codes."""

    overall_investment_score: Optional[float] = None
    liquidity_score: Optional[float] = None
    brand_score: Optional[float] = None
    risk_score: Optional[float] = None
    components: List[ScoreComponentContract] = Field(default_factory=list)


class RiskContract(BaseModel):
    """Risk surfaced from structured evidence."""

    code: str
    level: str
    source: str
    summary: str
    evidence_refs: List[EvidenceReferenceContract] = Field(default_factory=list)


class PricingGuidanceContract(BaseModel):
    """Pricing posture separated into retail, wholesale, BIN, and floor states."""

    pricing_strategy: str
    estimated_retail_range: Optional[ValueRangeContract] = None
    estimated_wholesale_range: Optional[ValueRangeContract] = None
    bin_price: Optional[MoneyContract] = None
    minimum_acceptable_offer: Optional[MoneyContract] = None
    listing_confidence: str
    notes: List[str] = Field(default_factory=list)


class FinalVerdictContract(BaseModel):
    """Deterministic final verdict for the appraisal."""

    status: str
    headline: str
    summary: str
    value_tier: Optional[str] = None
    pricing_posture: Optional[str] = None
    action: Optional[str] = None
    refusal_code: Optional[str] = None
    refusal_reason: Optional[str] = None


class FactSnapshotContract(BaseModel):
    """Small report-safe snapshot of a verified fact."""

    fact_id: str
    fact_type: str
    fact_key: str
    source_system: str
    observed_at: datetime


class SignalSnapshotContract(BaseModel):
    """Small report-safe snapshot of a derived signal."""

    signal_id: str
    signal_type: str
    signal_key: str
    confidence_score: Optional[float] = None
    generated_at: datetime


class AIExplanationSnippetContract(BaseModel):
    """Validated AI text included as a separately-labeled narrative layer."""

    explanation_id: str
    explanation_type: str
    model_name: str
    prompt_version: str
    validation_status: str
    text: str


class AppraisalReportContract(BaseModel):
    """Stored JSON contract for deterministic appraisal report output."""

    schema_version: str
    report_template_version: str
    generated_at: datetime
    valuation_status: str
    domain_header: DomainHeaderContract
    classification: ClassificationContract
    recommended_listing_price: Optional[MoneyContract] = None
    fair_market_range: Optional[ValueRangeContract] = None
    confidence_level: str
    whois_intelligence: WhoisIntelligenceContract
    tld_ecosystem_summary: TLDEcosystemSummaryContract
    market_analysis_summary: MarketAnalysisSummaryContract
    score_breakdown: ScoreBreakdownContract
    risks: List[RiskContract] = Field(default_factory=list)
    final_verdict: FinalVerdictContract
    pricing_guidance: PricingGuidanceContract
    supporting_facts: List[FactSnapshotContract] = Field(default_factory=list)
    derived_signals: List[SignalSnapshotContract] = Field(default_factory=list)
    validated_ai_explanations: List[AIExplanationSnippetContract] = Field(default_factory=list)
