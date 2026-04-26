"""Deterministic, explainable valuation and scoring engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from domain_intel.core.enums import (
    ConfidenceLevel,
    DomainType,
    ReasonDirection,
    ValuationRefusalCode,
    ValuationStatus,
    ValueTier,
)
from domain_intel.valuation.models import (
    ClassificationSnapshot,
    ComparableSalesSupport,
    ConfidenceAssessment,
    DomainValuationRequest,
    EvidenceRef,
    HistoricalSignals,
    InvestmentRecommendation,
    MarketDemandSignals,
    MoneyPoint,
    MoneyRange,
    RiskPenalty,
    RiskSignals,
    ScoreBreakdown,
    ScoreDimension,
    TldEcosystemSignals,
    ValuationReason,
    ValuationResult,
)
from domain_intel.valuation.profiles import resolve_weight_profile


TWO_PLACES = Decimal("0.01")
MAX_RISK_PENALTY_POINTS = 35.0
REFUSAL_DOMAIN_TYPES = {DomainType.TYPO_RISK}
REVIEW_DOMAIN_TYPES = {DomainType.ADULT_OR_SENSITIVE}

BASE_TLD_STRENGTH: Dict[str, float] = {
    "com": 0.90,
    "ai": 0.72,
    "io": 0.68,
    "org": 0.60,
    "co": 0.58,
    "net": 0.52,
    "app": 0.56,
    "xyz": 0.42,
}


@dataclass(frozen=True)
class NameFeatures:
    """Precomputed lexical features from the domain SLD."""

    tokens: Tuple[str, ...]
    normalized_sld: str
    letter_count: int
    full_length: int
    token_count: int
    has_hyphen: bool
    has_digits: bool
    vowel_ratio: float
    max_consonant_cluster: int
    unique_char_ratio: float


class RuleBasedValuationEngine:
    """Classification-aware domain valuation engine."""

    def describe_weights(self, domain_type: DomainType) -> Mapping[ScoreDimension, float]:
        """Expose the resolved weight map for audits and tests."""

        return resolve_weight_profile(domain_type).weights

    def build_refusal_result(
        self,
        request: DomainValuationRequest,
        refusal_code: ValuationRefusalCode,
        refusal_reason: str,
        remediation: Tuple[str, ...],
    ) -> ValuationResult:
        """Build a stable refusal result without pricing fields."""

        return ValuationResult(
            status=ValuationStatus.REFUSED,
            score=None,
            grade=None,
            confidence=ConfidenceAssessment(
                level=ConfidenceLevel.LOW,
                score=0.0,
                rationale=refusal_reason,
            ),
            value_tier=ValueTier.REFUSAL,
            domain_type=request.classification.domain_type if request.classification else None,
            estimated_value_min=None,
            estimated_value_max=None,
            estimated_value_point=None,
            wholesale_estimate=None,
            retail_estimate=None,
            bin_recommendation=None,
            minimum_acceptable_offer=None,
            hold_strategy="wait_for_verified_inputs",
            investment_recommendation=InvestmentRecommendation.PASS,
            pricing_basis="refusal",
            score_breakdown=tuple(),
            risk_penalties=tuple(),
            reason_codes=tuple(),
            classification_result_id=(
                request.classification.classification_result_id if request.classification else None
            ),
            refusal_code=refusal_code,
            refusal_reason=refusal_reason,
            remediation=remediation,
            input_fact_ids=request.input_fact_ids,
            input_signal_ids=request.input_signal_ids,
            algorithm_version=request.algorithm_version,
        )

    def value_domain(self, request: DomainValuationRequest) -> ValuationResult:
        """Value one domain using classification-aware rule logic."""

        if not request.domain.is_valid:
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.INVALID_DOMAIN,
                "The domain is not valid, so valuation is blocked.",
                ("Validate or normalize the canonical domain record first.",),
            )

        classification = request.classification
        if classification is None:
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.MISSING_CLASSIFICATION,
                "A current classification result is required before pricing.",
                ("Run classification for this domain.",),
            )

        if request.facts_are_stale:
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.STALE_INPUTS,
                "Pricing inputs are stale and should be refreshed before valuation.",
                ("Refresh domain enrichment and derived signals.",),
            )

        if request.has_conflicting_facts:
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.CONFLICTING_FACTS,
                "Pricing inputs conflict with one another, so the model cannot produce a reliable estimate.",
                ("Reconcile the conflicting facts or rerun enrichment.",),
            )

        if classification.domain_type in REFUSAL_DOMAIN_TYPES or classification.domain_type is DomainType.UNKNOWN:
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.UNSUPPORTED_DOMAIN_TYPE,
                "This domain type is not supported for automated pricing.",
                ("Route the domain to manual review or improve classification coverage.",),
            )

        legal_risk = self._resolve_legal_risk(classification, request.risk_signals)
        if legal_risk >= 0.85:
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.LEGAL_OR_TRADEMARK_RISK,
                "High legal or trademark risk blocks automated valuation.",
                ("Review trademark and legal risk before assigning a price.",),
            )

        comparable_support = request.comparable_support or ComparableSalesSupport()
        ecosystem_signals = request.ecosystem_signals or TldEcosystemSignals(tld=request.domain.tld)
        if self._is_data_too_thin(request, comparable_support, ecosystem_signals):
            return self.build_refusal_result(
                request,
                ValuationRefusalCode.INSUFFICIENT_EVIDENCE,
                "Data is too thin to support an explainable valuation.",
                (
                    "Add verified market, historical, or comparable-sale support.",
                    "Refresh ecosystem and enrichment signals.",
                ),
            )

        features = self._analyze_name(request.domain.sld, classification)
        weights = resolve_weight_profile(classification.domain_type).weights

        dimension_scores = self._build_dimension_breakdown(
            request=request,
            classification=classification,
            features=features,
            ecosystem_signals=ecosystem_signals,
            comparable_support=comparable_support,
            weights=weights,
        )
        positive_points = sum(item.weighted_points for item in dimension_scores)

        risk_penalties = self._build_risk_penalties(
            classification=classification,
            risk_signals=request.risk_signals,
            market_signals=request.market_signals,
            comparable_support=comparable_support,
        )
        total_penalty_points = min(
            MAX_RISK_PENALTY_POINTS,
            sum(item.points for item in risk_penalties),
        )
        score = int(round(self._clamp(positive_points - total_penalty_points, 0.0, 100.0)))

        heuristic_point = self._heuristic_retail_point(score, classification.domain_type)
        comparable_anchor = self._comparable_anchor_price(comparable_support, request.currency)
        comparable_quality = self._comparable_quality(comparable_support)
        retail_point, pricing_basis = self._blend_pricing(
            heuristic_point=heuristic_point,
            comparable_anchor=comparable_anchor,
            comparable_quality=comparable_quality,
            score=score,
            domain_type=classification.domain_type,
        )
        confidence = self._build_confidence(
            classification=classification,
            market_signals=request.market_signals,
            historical_signals=request.historical_signals,
            ecosystem_signals=ecosystem_signals,
            comparable_support=comparable_support,
            risk_penalties=risk_penalties,
            score=score,
        )
        retail_range = self._build_retail_range(
            retail_point=retail_point,
            currency=request.currency,
            confidence=confidence,
            comparable_quality=comparable_quality,
        )
        wholesale_range = self._build_wholesale_range(
            retail_point=retail_point,
            currency=request.currency,
            liquidity_score=self._dimension_score(dimension_scores, ScoreDimension.LIQUIDITY),
            confidence_score=confidence.score,
            total_penalty_points=total_penalty_points,
        )
        bin_recommendation = MoneyPoint(
            amount=self._money(retail_range.max_amount * Decimal("1.08")),
            currency=request.currency,
        )
        minimum_offer = MoneyPoint(
            amount=self._money(max(wholesale_range.max_amount, retail_range.min_amount * Decimal("0.70"))),
            currency=request.currency,
        )

        value_tier = self._value_tier(retail_range.point_amount)
        status = self._resolve_status(
            classification=classification,
            confidence=confidence,
            value_tier=value_tier,
            comparable_quality=comparable_quality,
            risk_penalties=risk_penalties,
        )
        reason_codes = self._build_reason_codes(
            dimension_scores=dimension_scores,
            risk_penalties=risk_penalties,
            retail_point=retail_range.point_amount,
            classification=classification,
            comparable_support=comparable_support,
            ecosystem_signals=ecosystem_signals,
            market_signals=request.market_signals,
            historical_signals=request.historical_signals,
        )

        return ValuationResult(
            status=status,
            score=score,
            grade=self._grade(score),
            confidence=confidence,
            value_tier=value_tier,
            domain_type=classification.domain_type,
            estimated_value_min=retail_range.min_amount,
            estimated_value_max=retail_range.max_amount,
            estimated_value_point=retail_range.point_amount,
            wholesale_estimate=wholesale_range,
            retail_estimate=retail_range,
            bin_recommendation=bin_recommendation,
            minimum_acceptable_offer=minimum_offer,
            hold_strategy=self._hold_strategy(
                status=status,
                value_tier=value_tier,
                confidence=confidence,
                liquidity_score=self._dimension_score(dimension_scores, ScoreDimension.LIQUIDITY),
            ),
            investment_recommendation=self._investment_recommendation(
                status=status,
                score=score,
                confidence=confidence,
                value_tier=value_tier,
                total_penalty_points=total_penalty_points,
            ),
            pricing_basis=pricing_basis,
            score_breakdown=tuple(dimension_scores),
            risk_penalties=tuple(risk_penalties),
            reason_codes=tuple(reason_codes),
            classification_result_id=classification.classification_result_id,
            refusal_code=None,
            refusal_reason=None,
            remediation=tuple(),
            input_fact_ids=request.input_fact_ids,
            input_signal_ids=request.input_signal_ids,
            algorithm_version=request.algorithm_version,
        )

    def _is_data_too_thin(
        self,
        request: DomainValuationRequest,
        comparable_support: ComparableSalesSupport,
        ecosystem_signals: TldEcosystemSignals,
    ) -> bool:
        return not any(
            (
                request.market_signals.has_data(),
                request.historical_signals.has_data(),
                comparable_support.has_data(),
                ecosystem_signals.has_provider_data(),
            )
        )

    def _build_dimension_breakdown(
        self,
        request: DomainValuationRequest,
        classification: ClassificationSnapshot,
        features: NameFeatures,
        ecosystem_signals: TldEcosystemSignals,
        comparable_support: ComparableSalesSupport,
        weights: Mapping[ScoreDimension, float],
    ) -> List[ScoreBreakdown]:
        pron_score = self._pronunciation_score(features, classification.domain_type)
        mem_score = self._memorability_score(features, pron_score)
        clarity_score = self._clarity_score(features, classification)
        brevity_score = self._brevity_score(features, classification.domain_type)
        semantic_score = self._semantic_score(features, classification, request.market_signals)
        brandability_score = self._brandability_score(
            features=features,
            domain_type=classification.domain_type,
            pronunciation_score=pron_score,
            memorability_score=mem_score,
            brevity_score=brevity_score,
        )
        commercial_score = self._commercial_demand_score(
            classification=classification,
            market_signals=request.market_signals,
            comparable_support=comparable_support,
        )
        tld_score = self._tld_strength_score(request.domain.tld, ecosystem_signals)
        upgrade_score = self._upgrade_target_score(
            classification=classification,
            domain_tld=request.domain.tld,
            ecosystem_signals=ecosystem_signals,
        )
        historical_score = self._historical_legitimacy_score(request.historical_signals)
        active_business_score = self._active_business_relevance_score(
            classification=classification,
            market_signals=request.market_signals,
        )
        comparable_score = self._comparable_support_score(comparable_support)
        trend_score = self._trend_relevance_score(request.market_signals)
        liquidity_score = self._liquidity_score(
            domain_type=classification.domain_type,
            tld_score=tld_score,
            brevity_score=brevity_score,
            commercial_score=commercial_score,
            comparable_score=comparable_score,
            provided_liquidity=request.market_signals.liquidity_score,
        )

        raw_scores = {
            ScoreDimension.PRONUNCIATION: (pron_score, self._pronunciation_explanation(features, pron_score), tuple()),
            ScoreDimension.MEMORABILITY: (mem_score, self._memorability_explanation(features, mem_score), tuple()),
            ScoreDimension.CLARITY: (clarity_score, self._clarity_explanation(classification, features), tuple()),
            ScoreDimension.BREVITY: (brevity_score, self._brevity_explanation(features), tuple()),
            ScoreDimension.SEMANTIC_COHERENCE: (
                semantic_score,
                self._semantic_explanation(classification, request.market_signals),
                request.market_signals.evidence_refs,
            ),
            ScoreDimension.BRANDABILITY: (
                brandability_score,
                self._brandability_explanation(classification.domain_type, brandability_score),
                tuple(),
            ),
            ScoreDimension.COMMERCIAL_DEMAND: (
                commercial_score,
                self._commercial_explanation(request.market_signals, comparable_support),
                self._merge_refs(request.market_signals.evidence_refs, comparable_support.evidence_refs),
            ),
            ScoreDimension.TLD_ECOSYSTEM_STRENGTH: (
                tld_score,
                self._tld_explanation(request.domain.tld, ecosystem_signals),
                ecosystem_signals.evidence_refs,
            ),
            ScoreDimension.UPGRADE_TARGET_STRENGTH: (
                upgrade_score,
                self._upgrade_explanation(ecosystem_signals),
                ecosystem_signals.evidence_refs,
            ),
            ScoreDimension.HISTORICAL_LEGITIMACY: (
                historical_score,
                self._historical_explanation(request.historical_signals),
                request.historical_signals.evidence_refs,
            ),
            ScoreDimension.ACTIVE_BUSINESS_RELEVANCE: (
                active_business_score,
                self._active_business_explanation(request.market_signals),
                request.market_signals.evidence_refs,
            ),
            ScoreDimension.COMPARABLE_SALES_SUPPORT: (
                comparable_score,
                self._comparable_explanation(comparable_support),
                self._merge_refs(comparable_support.evidence_refs, self._comparable_sale_refs(comparable_support)),
            ),
            ScoreDimension.TREND_RELEVANCE: (
                trend_score,
                self._trend_explanation(request.market_signals),
                request.market_signals.evidence_refs,
            ),
            ScoreDimension.LIQUIDITY: (
                liquidity_score,
                self._liquidity_explanation(liquidity_score, comparable_support),
                self._merge_refs(request.market_signals.evidence_refs, comparable_support.evidence_refs),
            ),
        }

        breakdown = []
        for dimension, weight in weights.items():
            score, explanation, refs = raw_scores[dimension]
            breakdown.append(
                ScoreBreakdown(
                    dimension=dimension,
                    weight=round(weight, 4),
                    score=round(score, 4),
                    weighted_points=round(weight * score, 4),
                    explanation=explanation,
                    evidence_refs=refs,
                )
            )
        return breakdown

    def _build_risk_penalties(
        self,
        classification: ClassificationSnapshot,
        risk_signals: RiskSignals,
        market_signals: MarketDemandSignals,
        comparable_support: ComparableSalesSupport,
    ) -> List[RiskPenalty]:
        penalties: List[RiskPenalty] = []
        legal_risk = self._resolve_legal_risk(classification, risk_signals)
        if 0.60 <= legal_risk < 0.85:
            penalties.append(
                RiskPenalty(
                    code="legal_risk_moderate",
                    label="Moderate legal risk",
                    points=15.0,
                    explanation="Trademark or legal ambiguity reduces valuation confidence and buyer pool depth.",
                )
            )

        typo_confusion = self._clamp(risk_signals.typo_confusion_score or 0.0)
        if 0.50 <= typo_confusion < 0.80:
            penalties.append(
                RiskPenalty(
                    code="typo_confusion",
                    label="Typo confusion risk",
                    points=10.0,
                    explanation="Potential confusion with a stronger underlying term reduces investability.",
                )
            )

        adult_risk = self._clamp(risk_signals.adult_sensitivity_score or 0.0)
        if adult_risk >= 0.45 or "adult_or_sensitive" in {flag.lower() for flag in classification.risk_flags}:
            penalties.append(
                RiskPenalty(
                    code="adult_sensitive",
                    label="Sensitive-content review risk",
                    points=8.0,
                    explanation="Sensitive-category exposure narrows demand and requires manual review.",
                )
            )

        trend_score = self._clamp(market_signals.trend_score or 0.0)
        commercial_score = self._clamp(market_signals.commercial_intent_score or 0.0)
        if trend_score >= 0.75 and commercial_score < 0.45 and not comparable_support.has_data():
            penalties.append(
                RiskPenalty(
                    code="trend_overhang",
                    label="Trend-only support",
                    points=5.0,
                    explanation="Trend alignment exists, but it is not supported by deeper commercial or comparable evidence.",
                )
            )

        return penalties

    def _build_confidence(
        self,
        classification: ClassificationSnapshot,
        market_signals: MarketDemandSignals,
        historical_signals: HistoricalSignals,
        ecosystem_signals: TldEcosystemSignals,
        comparable_support: ComparableSalesSupport,
        risk_penalties: Iterable[RiskPenalty],
        score: int,
    ) -> ConfidenceAssessment:
        comparable_quality = self._comparable_quality(comparable_support)
        evidence_coverage = (
            (1.0 if market_signals.has_data() else 0.15)
            + (1.0 if historical_signals.has_data() else 0.15)
            + (1.0 if ecosystem_signals.has_provider_data() else 0.25)
            + (comparable_quality if comparable_support.has_data() else 0.10)
        ) / 4.0
        risk_penalty_points = sum(item.points for item in risk_penalties)
        consistency = self._clamp(1.0 - (risk_penalty_points / 35.0))
        score_support = self._clamp(score / 100.0)
        confidence_score = self._clamp(
            (classification.confidence_score * 0.38)
            + (evidence_coverage * 0.30)
            + (comparable_quality * 0.17)
            + (consistency * 0.10)
            + (score_support * 0.05)
        )

        if confidence_score >= 0.74:
            level = ConfidenceLevel.HIGH
        elif confidence_score >= 0.48:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        rationale_parts = []
        if classification.confidence_score >= 0.75:
            rationale_parts.append("classification support is strong")
        elif classification.confidence_score >= 0.50:
            rationale_parts.append("classification support is usable")
        else:
            rationale_parts.append("classification support is weak")

        if comparable_support.has_data():
            rationale_parts.append(f"{len(comparable_support.sales)} comparable sale(s) are available")
        else:
            rationale_parts.append("comparable-sale support is missing")

        if market_signals.has_data() or historical_signals.has_data() or ecosystem_signals.has_provider_data():
            rationale_parts.append("supplementary market evidence is present")
        else:
            rationale_parts.append("supplementary market evidence is limited")

        if risk_penalty_points:
            rationale_parts.append("risk penalties reduce certainty")

        return ConfidenceAssessment(
            level=level,
            score=round(confidence_score, 4),
            rationale=", ".join(rationale_parts) + ".",
        )

    def _resolve_status(
        self,
        classification: ClassificationSnapshot,
        confidence: ConfidenceAssessment,
        value_tier: ValueTier,
        comparable_quality: float,
        risk_penalties: Iterable[RiskPenalty],
    ) -> ValuationStatus:
        penalty_total = sum(item.points for item in risk_penalties)
        if classification.domain_type in REVIEW_DOMAIN_TYPES:
            return ValuationStatus.NEEDS_REVIEW
        if confidence.level is ConfidenceLevel.LOW:
            return ValuationStatus.NEEDS_REVIEW
        if value_tier in {ValueTier.HIGH, ValueTier.PREMIUM} and comparable_quality < 0.35:
            return ValuationStatus.NEEDS_REVIEW
        if penalty_total >= 18:
            return ValuationStatus.NEEDS_REVIEW
        return ValuationStatus.VALUED

    def _build_reason_codes(
        self,
        dimension_scores: List[ScoreBreakdown],
        risk_penalties: List[RiskPenalty],
        retail_point: Decimal,
        classification: ClassificationSnapshot,
        comparable_support: ComparableSalesSupport,
        ecosystem_signals: TldEcosystemSignals,
        market_signals: MarketDemandSignals,
        historical_signals: HistoricalSignals,
    ) -> List[ValuationReason]:
        positive_items = sorted(
            (item for item in dimension_scores if item.score >= 0.65),
            key=lambda item: item.weighted_points,
            reverse=True,
        )[:3]
        negative_items = sorted(
            (item for item in dimension_scores if item.score <= 0.45),
            key=lambda item: item.weighted_points,
        )[:2]

        reasons: List[ValuationReason] = []
        for item in positive_items:
            impact_weight = round(item.weighted_points / 100.0, 4)
            reasons.append(
                ValuationReason(
                    code=item.dimension.value,
                    label=item.dimension.value.replace("_", " ").title(),
                    direction=ReasonDirection.POSITIVE,
                    impact_weight=impact_weight,
                    impact_amount=self._money(retail_point * Decimal(str(impact_weight))),
                    explanation=item.explanation,
                    evidence_refs=item.evidence_refs,
                )
            )

        for item in negative_items:
            impact_weight = round(((1.0 - item.score) * item.weight) / 100.0, 4)
            reasons.append(
                ValuationReason(
                    code=f"{item.dimension.value}_drag",
                    label=item.dimension.value.replace("_", " ").title(),
                    direction=ReasonDirection.NEGATIVE,
                    impact_weight=impact_weight,
                    impact_amount=self._money(retail_point * Decimal(str(impact_weight))),
                    explanation=item.explanation,
                    evidence_refs=item.evidence_refs,
                )
            )

        for penalty in risk_penalties:
            impact_weight = round(penalty.points / 100.0, 4)
            reasons.append(
                ValuationReason(
                    code=penalty.code,
                    label=penalty.label,
                    direction=ReasonDirection.NEGATIVE,
                    impact_weight=impact_weight,
                    impact_amount=self._money(retail_point * Decimal(str(impact_weight))),
                    explanation=penalty.explanation,
                )
            )

        if comparable_support.has_data():
            reasons.append(
                ValuationReason(
                    code="comparable_support_present",
                    label="Comparable support present",
                    direction=ReasonDirection.NEUTRAL,
                    impact_weight=round(self._comparable_quality(comparable_support) / 10.0, 4),
                    impact_amount=None,
                    explanation=f"{len(comparable_support.sales)} comparable sale(s) support the price range.",
                    evidence_refs=self._merge_refs(
                        comparable_support.evidence_refs,
                        self._comparable_sale_refs(comparable_support),
                    ),
                )
            )
        elif ecosystem_signals.has_provider_data() or market_signals.has_data() or historical_signals.has_data():
            reasons.append(
                ValuationReason(
                    code="heuristic_without_comparables",
                    label="Heuristic pricing",
                    direction=ReasonDirection.NEUTRAL,
                    impact_weight=0.02,
                    impact_amount=None,
                    explanation="Pricing uses classification, ecosystem, and market evidence without verified comparable sales.",
                )
            )

        reasons.append(
            ValuationReason(
                code=f"classification_{classification.domain_type.value}",
                label="Classification profile applied",
                direction=ReasonDirection.NEUTRAL,
                impact_weight=round(classification.confidence_score / 10.0, 4),
                impact_amount=None,
                explanation=f"Scoring weights were adjusted for the {classification.domain_type.value} class.",
            )
        )
        return reasons

    def _heuristic_retail_point(self, score: int, domain_type: DomainType) -> Decimal:
        if score < 20:
            base = Decimal("75")
        elif score < 35:
            base = Decimal("100") + (Decimal(score - 20) * Decimal("12"))
        elif score < 50:
            base = Decimal("280") + (Decimal(score - 35) * Decimal("26"))
        elif score < 65:
            base = Decimal("700") + (Decimal(score - 50) * Decimal("72"))
        elif score < 80:
            base = Decimal("1800") + (Decimal(score - 65) * Decimal("225"))
        elif score < 90:
            base = Decimal("5200") + (Decimal(score - 80) * Decimal("640"))
        else:
            base = Decimal("11600") + (Decimal(score - 90) * Decimal("1800"))

        multiplier = {
            DomainType.EXACT_MATCH: Decimal("1.12"),
            DomainType.PREMIUM_GENERIC: Decimal("1.08"),
            DomainType.GEO: Decimal("1.00"),
            DomainType.KEYWORD_PHRASE: Decimal("0.94"),
            DomainType.BRANDABLE: Decimal("0.92"),
            DomainType.ACRONYM: Decimal("0.95"),
            DomainType.NUMERIC: Decimal("0.75"),
            DomainType.PERSONAL_NAME: Decimal("0.70"),
        }.get(domain_type, Decimal("1.00"))
        return self._money(base * multiplier)

    def _blend_pricing(
        self,
        heuristic_point: Decimal,
        comparable_anchor: Optional[Decimal],
        comparable_quality: float,
        score: int,
        domain_type: DomainType,
    ) -> Tuple[Decimal, str]:
        if comparable_anchor is None or comparable_quality < 0.20:
            return heuristic_point, "heuristic"

        blend = self._clamp(0.35 + (comparable_quality * 0.35))
        if score >= 80 and domain_type in {DomainType.EXACT_MATCH, DomainType.PREMIUM_GENERIC}:
            blend = self._clamp(blend + 0.10)
        retail_point = self._money(
            (heuristic_point * Decimal(str(1.0 - blend)))
            + (comparable_anchor * Decimal(str(blend)))
        )
        if blend >= 0.60:
            return retail_point, "comparable_anchored"
        return retail_point, "hybrid"

    def _build_retail_range(
        self,
        retail_point: Decimal,
        currency: str,
        confidence: ConfidenceAssessment,
        comparable_quality: float,
    ) -> MoneyRange:
        spread = self._clamp(0.60 - (confidence.score * 0.28) - (comparable_quality * 0.12), 0.22, 0.60)
        min_amount = self._money(retail_point * Decimal(str(1.0 - (spread / 2.0))))
        max_amount = self._money(retail_point * Decimal(str(1.0 + (spread / 2.0))))
        return MoneyRange(min_amount=min_amount, max_amount=max_amount, currency=currency)

    def _build_wholesale_range(
        self,
        retail_point: Decimal,
        currency: str,
        liquidity_score: float,
        confidence_score: float,
        total_penalty_points: float,
    ) -> MoneyRange:
        ratio = self._clamp(
            0.18 + (liquidity_score * 0.14) + (confidence_score * 0.08) - (total_penalty_points / 200.0),
            0.12,
            0.40,
        )
        wholesale_point = retail_point * Decimal(str(ratio))
        return MoneyRange(
            min_amount=self._money(wholesale_point * Decimal("0.88")),
            max_amount=self._money(wholesale_point * Decimal("1.12")),
            currency=currency,
        )

    def _value_tier(self, retail_point: Decimal) -> ValueTier:
        if retail_point >= Decimal("10000"):
            return ValueTier.PREMIUM
        if retail_point >= Decimal("2500"):
            return ValueTier.HIGH
        if retail_point >= Decimal("500"):
            return ValueTier.MEANINGFUL
        return ValueTier.LOW

    def _hold_strategy(
        self,
        status: ValuationStatus,
        value_tier: ValueTier,
        confidence: ConfidenceAssessment,
        liquidity_score: float,
    ) -> str:
        if status is ValuationStatus.NEEDS_REVIEW:
            return "review pricing manually before acquisition or listing"
        if value_tier is ValueTier.PREMIUM:
            return "acquire selectively and hold 18 to 36 months for end-user outreach"
        if value_tier is ValueTier.HIGH and confidence.level is not ConfidenceLevel.LOW:
            return "hold 12 to 24 months with a visible BIN and negotiation room"
        if value_tier is ValueTier.MEANINGFUL and liquidity_score >= 0.55:
            return "list with BIN and expect investor liquidity before patient end-user upside"
        if value_tier is ValueTier.MEANINGFUL:
            return "hold patiently and only accept offers near retail support"
        return "keep only if acquired cheaply, otherwise pass or liquidate fast"

    def _investment_recommendation(
        self,
        status: ValuationStatus,
        score: int,
        confidence: ConfidenceAssessment,
        value_tier: ValueTier,
        total_penalty_points: float,
    ) -> InvestmentRecommendation:
        if status is ValuationStatus.NEEDS_REVIEW and confidence.level is ConfidenceLevel.LOW:
            return InvestmentRecommendation.PASS
        if score >= 82 and confidence.level is ConfidenceLevel.HIGH and total_penalty_points <= 6:
            return InvestmentRecommendation.STRONG_BUY
        if score >= 68 and value_tier in {ValueTier.MEANINGFUL, ValueTier.HIGH, ValueTier.PREMIUM}:
            return InvestmentRecommendation.BUY
        if score >= 52:
            return InvestmentRecommendation.HOLD
        return InvestmentRecommendation.PASS

    def _grade(self, score: int) -> str:
        if score >= 80:
            return "A"
        if score >= 65:
            return "B"
        if score >= 50:
            return "C"
        if score >= 35:
            return "D"
        return "F"

    def _comparable_quality(self, comparable_support: ComparableSalesSupport) -> float:
        if comparable_support.quality_score is not None:
            return self._clamp(comparable_support.quality_score)
        if not comparable_support.sales:
            return 0.0
        similarity = self._average(sale.similarity_score for sale in comparable_support.sales)
        same_tld = self._average(1.0 if sale.same_tld else 0.7 for sale in comparable_support.sales)
        count_score = min(len(comparable_support.sales) / 5.0, 1.0)
        return self._clamp((similarity * 0.45) + (same_tld * 0.20) + (count_score * 0.35))

    def _comparable_anchor_price(
        self,
        comparable_support: ComparableSalesSupport,
        currency: str,
    ) -> Optional[Decimal]:
        weighted_total = Decimal("0")
        weight_total = Decimal("0")
        for sale in comparable_support.sales:
            if sale.currency != currency:
                continue
            weight = Decimal(str(self._clamp(sale.similarity_score))) * (
                Decimal("1.0") if sale.same_tld else Decimal("0.75")
            )
            weighted_total += sale.price * weight
            weight_total += weight
        if weight_total == 0:
            return None
        return self._money(weighted_total / weight_total)

    def _analyze_name(self, sld: str, classification: ClassificationSnapshot) -> NameFeatures:
        normalized = sld.lower()
        token_candidates = classification.tokens or tuple(
            part for part in re.split(r"[^a-z0-9]+", normalized) if part
        )
        tokens = tuple(token for token in token_candidates if token)
        letters_only = re.sub(r"[^a-z]", "", normalized)
        consonant_clusters = re.findall(r"[^aeiou]+", letters_only)
        unique_char_ratio = (
            len(set(letters_only)) / len(letters_only)
            if letters_only
            else 0.0
        )
        vowels = len(re.findall(r"[aeiou]", letters_only))
        return NameFeatures(
            tokens=tokens or (normalized,),
            normalized_sld=normalized,
            letter_count=len(letters_only),
            full_length=len(normalized),
            token_count=len(tokens or (normalized,)),
            has_hyphen="-" in normalized,
            has_digits=any(char.isdigit() for char in normalized),
            vowel_ratio=(vowels / len(letters_only)) if letters_only else 0.0,
            max_consonant_cluster=max((len(cluster) for cluster in consonant_clusters), default=0),
            unique_char_ratio=unique_char_ratio,
        )

    def _pronunciation_score(self, features: NameFeatures, domain_type: DomainType) -> float:
        if domain_type is DomainType.NUMERIC:
            return 0.10
        score = 0.55
        if features.has_digits:
            score -= 0.25
        if features.has_hyphen:
            score -= 0.12
        if 0.28 <= features.vowel_ratio <= 0.62:
            score += 0.18
        else:
            score -= 0.12
        if features.max_consonant_cluster <= 3:
            score += 0.12
        else:
            score -= 0.18
        if 4 <= features.letter_count <= 10:
            score += 0.10
        elif features.letter_count > 15:
            score -= 0.10
        if domain_type is DomainType.BRANDABLE:
            score += 0.05
        if domain_type is DomainType.ACRONYM:
            score = min(score, 0.45)
        return self._clamp(score)

    def _memorability_score(self, features: NameFeatures, pronunciation_score: float) -> float:
        score = 0.30 + (pronunciation_score * 0.20)
        if features.letter_count <= 8:
            score += 0.28
        elif features.letter_count <= 12:
            score += 0.16
        elif features.letter_count > 16:
            score -= 0.15
        if features.token_count == 1:
            score += 0.15
        elif features.token_count == 2:
            score += 0.08
        else:
            score -= 0.10
        if 0.45 <= features.unique_char_ratio <= 0.82:
            score += 0.08
        if features.has_hyphen:
            score -= 0.08
        if features.has_digits:
            score -= 0.10
        return self._clamp(score)

    def _clarity_score(self, features: NameFeatures, classification: ClassificationSnapshot) -> float:
        score = 0.40
        if features.has_digits:
            score -= 0.18
        if features.has_hyphen:
            score -= 0.12
        if features.token_count <= 2:
            score += 0.12
        if classification.domain_type in {
            DomainType.EXACT_MATCH,
            DomainType.GEO,
            DomainType.KEYWORD_PHRASE,
            DomainType.PREMIUM_GENERIC,
        }:
            score += 0.22
        elif classification.domain_type is DomainType.BRANDABLE:
            score += 0.06
        if classification.business_category:
            score += 0.05
        return self._clamp(score)

    def _brevity_score(self, features: NameFeatures, domain_type: DomainType) -> float:
        target_length = {
            DomainType.BRANDABLE: 6,
            DomainType.ACRONYM: 4,
            DomainType.NUMERIC: 4,
            DomainType.GEO: 11,
            DomainType.KEYWORD_PHRASE: 12,
            DomainType.EXACT_MATCH: 8,
            DomainType.PREMIUM_GENERIC: 8,
            DomainType.PERSONAL_NAME: 10,
        }.get(domain_type, 9)
        span = {
            DomainType.BRANDABLE: 8,
            DomainType.ACRONYM: 4,
            DomainType.NUMERIC: 5,
            DomainType.GEO: 12,
            DomainType.KEYWORD_PHRASE: 14,
            DomainType.EXACT_MATCH: 10,
            DomainType.PREMIUM_GENERIC: 10,
            DomainType.PERSONAL_NAME: 12,
        }.get(domain_type, 10)
        score = 1.0 - (abs(features.letter_count - target_length) / max(span, 1))
        if features.has_hyphen:
            score -= 0.08
        if features.has_digits:
            score -= 0.10
        return self._clamp(score)

    def _semantic_score(
        self,
        features: NameFeatures,
        classification: ClassificationSnapshot,
        market_signals: MarketDemandSignals,
    ) -> float:
        score = {
            DomainType.EXACT_MATCH: 0.82,
            DomainType.PREMIUM_GENERIC: 0.78,
            DomainType.GEO: 0.72,
            DomainType.KEYWORD_PHRASE: 0.68,
            DomainType.BRANDABLE: 0.55,
            DomainType.ACRONYM: 0.42,
            DomainType.NUMERIC: 0.35,
            DomainType.PERSONAL_NAME: 0.48,
        }.get(classification.domain_type, 0.40)
        if features.token_count == 2 and classification.domain_type in {DomainType.GEO, DomainType.KEYWORD_PHRASE}:
            score += 0.05
        if market_signals.commercial_intent_score is not None:
            score += market_signals.commercial_intent_score * 0.08
        if features.has_hyphen:
            score -= 0.08
        return self._clamp(score)

    def _brandability_score(
        self,
        features: NameFeatures,
        domain_type: DomainType,
        pronunciation_score: float,
        memorability_score: float,
        brevity_score: float,
    ) -> float:
        score = 0.20
        if domain_type is DomainType.BRANDABLE:
            score += 0.38
        elif domain_type in {DomainType.EXACT_MATCH, DomainType.PREMIUM_GENERIC}:
            score += 0.15
        elif domain_type is DomainType.ACRONYM:
            score += 0.12
        score += pronunciation_score * 0.15
        score += memorability_score * 0.10
        score += brevity_score * 0.10
        if features.token_count > 2:
            score -= 0.15
        if features.has_hyphen or features.has_digits:
            score -= 0.10
        if domain_type in {DomainType.GEO, DomainType.KEYWORD_PHRASE, DomainType.NUMERIC}:
            score = min(score, 0.58)
        return self._clamp(score)

    def _commercial_demand_score(
        self,
        classification: ClassificationSnapshot,
        market_signals: MarketDemandSignals,
        comparable_support: ComparableSalesSupport,
    ) -> float:
        heuristic = {
            DomainType.EXACT_MATCH: 0.78,
            DomainType.PREMIUM_GENERIC: 0.74,
            DomainType.GEO: 0.68,
            DomainType.KEYWORD_PHRASE: 0.60,
            DomainType.BRANDABLE: 0.54,
            DomainType.ACRONYM: 0.52,
            DomainType.NUMERIC: 0.32,
            DomainType.PERSONAL_NAME: 0.30,
        }.get(classification.domain_type, 0.28)
        provided_scores = [
            score
            for score in (
                market_signals.commercial_intent_score,
                market_signals.search_demand_score,
                market_signals.active_business_score,
            )
            if score is not None
        ]
        if provided_scores:
            heuristic = (heuristic * 0.45) + (self._average(provided_scores) * 0.55)
        if market_signals.active_business_count:
            heuristic += min(market_signals.active_business_count / 40.0, 0.12)
        if comparable_support.has_data():
            heuristic += 0.05
        return self._clamp(heuristic)

    def _tld_strength_score(self, tld: str, ecosystem_signals: TldEcosystemSignals) -> float:
        base = BASE_TLD_STRENGTH.get(tld.lower().lstrip("."), 0.38)
        provider_scores = [
            score
            for score in (
                ecosystem_signals.registry_strength_score,
                ecosystem_signals.aftermarket_liquidity_score,
                ecosystem_signals.end_user_adoption_score,
            )
            if score is not None
        ]
        if provider_scores:
            return self._clamp((base * 0.45) + (self._average(provider_scores) * 0.55))
        return self._clamp(base)

    def _upgrade_target_score(
        self,
        classification: ClassificationSnapshot,
        domain_tld: str,
        ecosystem_signals: TldEcosystemSignals,
    ) -> float:
        score = {
            DomainType.EXACT_MATCH: 0.68,
            DomainType.PREMIUM_GENERIC: 0.64,
            DomainType.GEO: 0.62,
            DomainType.KEYWORD_PHRASE: 0.54,
            DomainType.BRANDABLE: 0.50,
            DomainType.ACRONYM: 0.42,
            DomainType.NUMERIC: 0.28,
            DomainType.PERSONAL_NAME: 0.25,
        }.get(classification.domain_type, 0.30)
        if domain_tld.lower().lstrip(".") == "com":
            score += 0.05
        if ecosystem_signals.upgrade_target_score is not None:
            score = (score * 0.40) + (ecosystem_signals.upgrade_target_score * 0.60)
        if ecosystem_signals.registered_extension_count:
            score += min(ecosystem_signals.registered_extension_count / 50.0, 0.08)
        return self._clamp(score)

    def _historical_legitimacy_score(self, historical_signals: HistoricalSignals) -> float:
        if not historical_signals.has_data():
            return 0.26
        score = 0.20
        if historical_signals.years_since_first_seen is not None:
            score += min(historical_signals.years_since_first_seen / 18.0, 1.0) * 0.25
        if historical_signals.active_website_years is not None:
            score += min(historical_signals.active_website_years / 10.0, 1.0) * 0.25
        if historical_signals.archive_snapshot_count is not None:
            score += min(historical_signals.archive_snapshot_count / 15.0, 1.0) * 0.20
        if historical_signals.website_resolves is True:
            score += 0.18
        return self._clamp(score)

    def _active_business_relevance_score(
        self,
        classification: ClassificationSnapshot,
        market_signals: MarketDemandSignals,
    ) -> float:
        heuristic = {
            DomainType.EXACT_MATCH: 0.72,
            DomainType.PREMIUM_GENERIC: 0.64,
            DomainType.GEO: 0.70,
            DomainType.KEYWORD_PHRASE: 0.60,
            DomainType.BRANDABLE: 0.42,
            DomainType.ACRONYM: 0.40,
            DomainType.NUMERIC: 0.20,
            DomainType.PERSONAL_NAME: 0.22,
        }.get(classification.domain_type, 0.20)
        if market_signals.active_business_score is not None:
            heuristic = (heuristic * 0.45) + (market_signals.active_business_score * 0.55)
        if market_signals.active_business_count:
            heuristic += min(market_signals.active_business_count / 50.0, 0.15)
        return self._clamp(heuristic)

    def _comparable_support_score(self, comparable_support: ComparableSalesSupport) -> float:
        if not comparable_support.has_data():
            return 0.12
        return self._comparable_quality(comparable_support)

    def _trend_relevance_score(self, market_signals: MarketDemandSignals) -> float:
        if market_signals.trend_score is None:
            return 0.15
        return self._clamp(market_signals.trend_score)

    def _liquidity_score(
        self,
        domain_type: DomainType,
        tld_score: float,
        brevity_score: float,
        commercial_score: float,
        comparable_score: float,
        provided_liquidity: Optional[float],
    ) -> float:
        base = (
            (tld_score * 0.30)
            + (brevity_score * 0.25)
            + (commercial_score * 0.25)
            + (comparable_score * 0.20)
        )
        if domain_type in {DomainType.EXACT_MATCH, DomainType.PREMIUM_GENERIC, DomainType.BRANDABLE, DomainType.ACRONYM}:
            base += 0.05
        if provided_liquidity is not None:
            base = (base * 0.55) + (provided_liquidity * 0.45)
        return self._clamp(base)

    def _pronunciation_explanation(self, features: NameFeatures, score: float) -> str:
        return (
            f"{features.letter_count}-letter string with vowel ratio {features.vowel_ratio:.2f} "
            f"and max consonant cluster {features.max_consonant_cluster}; pronounceability is {self._label(score)}."
        )

    def _memorability_explanation(self, features: NameFeatures, score: float) -> str:
        return (
            f"{features.token_count} token(s) and unique-char ratio {features.unique_char_ratio:.2f}; "
            f"memorability is {self._label(score)}."
        )

    def _clarity_explanation(self, classification: ClassificationSnapshot, features: NameFeatures) -> str:
        return (
            f"Classification is {classification.domain_type.value} with {features.token_count} token(s); "
            f"structure is {'clean' if not features.has_hyphen and not features.has_digits else 'noisy'}."
        )

    def _brevity_explanation(self, features: NameFeatures) -> str:
        return f"SLD length is {features.letter_count} letters and {features.full_length} characters total."

    def _semantic_explanation(self, classification: ClassificationSnapshot, market_signals: MarketDemandSignals) -> str:
        if market_signals.commercial_intent_score is not None:
            return (
                f"{classification.domain_type.value} classification with commercial-intent support "
                f"of {market_signals.commercial_intent_score:.2f}."
            )
        return f"{classification.domain_type.value} classification drives semantic fit."

    def _brandability_explanation(self, domain_type: DomainType, score: float) -> str:
        return f"{domain_type.value} profile yields {self._label(score)} brandability."

    def _commercial_explanation(
        self,
        market_signals: MarketDemandSignals,
        comparable_support: ComparableSalesSupport,
    ) -> str:
        parts = []
        if market_signals.commercial_intent_score is not None:
            parts.append(f"commercial intent {market_signals.commercial_intent_score:.2f}")
        if market_signals.active_business_count is not None:
            parts.append(f"{market_signals.active_business_count} active business signals")
        if comparable_support.has_data():
            parts.append(f"{len(comparable_support.sales)} comparable sale(s)")
        if not parts:
            return "Commercial demand is estimated from domain type and structure only."
        return "Commercial demand uses " + ", ".join(parts) + "."

    def _tld_explanation(self, tld: str, ecosystem_signals: TldEcosystemSignals) -> str:
        if ecosystem_signals.has_provider_data():
            return f".{tld.lstrip('.')} uses provider-backed ecosystem strength inputs."
        return f".{tld.lstrip('.')} uses baseline TLD strength heuristics only."

    def _upgrade_explanation(self, ecosystem_signals: TldEcosystemSignals) -> str:
        if ecosystem_signals.upgrade_target_score is not None:
            return f"Provider upgrade-target score is {ecosystem_signals.upgrade_target_score:.2f}."
        if ecosystem_signals.registered_extension_count is not None:
            return f"Registered extension count is {ecosystem_signals.registered_extension_count}, capped to avoid overvaluation."
        return "Upgrade-target strength uses conservative domain-type heuristics."

    def _historical_explanation(self, historical_signals: HistoricalSignals) -> str:
        if not historical_signals.has_data():
            return "Historical legitimacy is lightly supported because direct evidence is limited."
        parts = []
        if historical_signals.years_since_first_seen is not None:
            parts.append(f"{historical_signals.years_since_first_seen:.1f} years observed")
        if historical_signals.active_website_years is not None:
            parts.append(f"{historical_signals.active_website_years:.1f} years of active website history")
        if historical_signals.archive_snapshot_count is not None:
            parts.append(f"{historical_signals.archive_snapshot_count} archive snapshots")
        if historical_signals.website_resolves is True:
            parts.append("current website resolves")
        return "Historical legitimacy uses " + ", ".join(parts) + "."

    def _active_business_explanation(self, market_signals: MarketDemandSignals) -> str:
        if market_signals.active_business_score is not None:
            return f"Active business score is {market_signals.active_business_score:.2f}."
        if market_signals.active_business_count is not None:
            return f"Active business count is {market_signals.active_business_count}."
        return "Active business relevance falls back to classification heuristics."

    def _comparable_explanation(self, comparable_support: ComparableSalesSupport) -> str:
        if comparable_support.has_data():
            return (
                f"{len(comparable_support.sales)} comparable sale(s) with quality "
                f"{self._comparable_quality(comparable_support):.2f}."
            )
        return "Comparable-sale support is absent, so this dimension remains conservative."

    def _trend_explanation(self, market_signals: MarketDemandSignals) -> str:
        if market_signals.trend_score is not None:
            return f"Trend relevance score is {market_signals.trend_score:.2f} and carries limited weight."
        return "Trend relevance is neutral because no explicit trend signal was supplied."

    def _liquidity_explanation(self, liquidity_score: float, comparable_support: ComparableSalesSupport) -> str:
        if comparable_support.has_data():
            return f"Liquidity is {self._label(liquidity_score)} with comparable-market support."
        return f"Liquidity is {self._label(liquidity_score)} from structure, TLD, and demand heuristics."

    def _resolve_legal_risk(self, classification: ClassificationSnapshot, risk_signals: RiskSignals) -> float:
        flags = {flag.lower() for flag in classification.risk_flags}
        if {"trademark_exact", "trademark_known", "legal_risk_high"} & flags:
            return 1.0
        return self._clamp(risk_signals.trademark_risk_score or 0.0)

    def _dimension_score(
        self,
        dimension_scores: Iterable[ScoreBreakdown],
        target: ScoreDimension,
    ) -> float:
        for item in dimension_scores:
            if item.dimension is target:
                return item.score
        return 0.0

    def _merge_refs(self, *groups: Tuple[EvidenceRef, ...]) -> Tuple[EvidenceRef, ...]:
        merged: List[EvidenceRef] = []
        seen = set()
        for group in groups:
            for ref in group:
                key = (ref.type, ref.id, ref.source)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(ref)
        return tuple(merged)

    def _comparable_sale_refs(self, comparable_support: ComparableSalesSupport) -> Tuple[EvidenceRef, ...]:
        refs: List[EvidenceRef] = []
        for sale in comparable_support.sales:
            refs.extend(sale.evidence_refs)
        return tuple(refs)

    def _average(self, values: Iterable[float]) -> float:
        values_list = list(values)
        if not values_list:
            return 0.0
        return sum(values_list) / len(values_list)

    def _label(self, score: float) -> str:
        if score >= 0.75:
            return "strong"
        if score >= 0.50:
            return "moderate"
        return "weak"

    def _money(self, value: Decimal) -> Decimal:
        return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def _clamp(self, value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))
