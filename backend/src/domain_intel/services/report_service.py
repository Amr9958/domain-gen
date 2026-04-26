"""Appraisal report assembly and retrieval service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence
from uuid import UUID

from domain_intel.contracts.appraisal import (
    AIExplanationSnippetContract,
    AppraisalReportContract,
    ClassificationContract,
    DomainHeaderContract,
    EvidenceReferenceContract,
    FactSnapshotContract,
    FinalVerdictContract,
    MarketAnalysisSummaryContract,
    MoneyContract,
    PricingGuidanceContract,
    RiskContract,
    ScoreBreakdownContract,
    ScoreComponentContract,
    SignalSnapshotContract,
    TLDEcosystemSummaryContract,
    ValueRangeContract,
    WhoisIntelligenceContract,
)
from domain_intel.core.enums import AppraisalReportStatus, ValuationStatus


WHOIS_FIELD_ALIASES = {
    "registrar": {"registrar", "whois_registrar"},
    "created_at": {"created_at", "creation_date", "registered_at", "whois_created_at"},
    "updated_at": {"updated_at", "updated_date", "whois_updated_at"},
    "expires_at": {"expires_at", "expiration_date", "expiry_date", "whois_expires_at"},
    "status_labels": {"status", "statuses", "status_labels", "domain_status"},
    "nameservers": {"nameservers", "name_servers"},
    "privacy_protected": {"privacy_protected", "whois_privacy", "privacy_enabled"},
    "registrant_country": {"registrant_country", "country"},
}

TLD_FIELD_ALIASES = {
    "registered_extensions": {"registered_extensions", "registered_tlds", "sibling_extensions"},
    "active_website_extensions": {"active_website_extensions", "live_extensions"},
    "parked_extensions": {"parked_extensions"},
    "extension_count": {"extension_count", "registered_extension_count"},
    "narrative_flags": {"tld_ecosystem_flags", "ecosystem_flags", "tld_notes"},
}

WHOLESALE_SIGNAL_KEYS = {
    "estimated_wholesale_point",
    "estimated_wholesale_value",
    "wholesale_estimate",
}
WHOLESALE_RANGE_LOW_KEYS = {
    "estimated_wholesale_min",
    "wholesale_estimate_min",
}
WHOLESALE_RANGE_HIGH_KEYS = {
    "estimated_wholesale_max",
    "wholesale_estimate_max",
}
NUMERIC_SCORE_SIGNAL_KEYS = {
    "investment_score": "Overall Investment Score",
    "liquidity_score": "Liquidity Score",
    "brand_score": "Brand Score",
    "risk_score": "Risk Score",
}
MARKET_SIGNAL_KEYS = {
    "search_demand_band",
    "commercial_intent",
    "auction_interest_band",
    "upgrade_candidate_summary",
}


@dataclass(frozen=True)
class ReportDomainInput:
    """Canonical domain input for report composition."""

    id: UUID
    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: Optional[str]
    is_valid: bool


@dataclass(frozen=True)
class ReportAuctionInput:
    """Optional auction context attached to a valuation."""

    id: UUID
    marketplace_code: Optional[str]
    auction_type: str
    status: str
    source_url: Optional[str]
    ends_at: Optional[datetime]
    current_bid_amount: Optional[Decimal]
    currency: Optional[str]
    bid_count: Optional[int]
    watchers_count: Optional[int]


@dataclass(frozen=True)
class ReportClassificationInput:
    """Classification snapshot consumed by the report composer."""

    id: UUID
    domain_type: Optional[str]
    business_category: Optional[str]
    language_code: Optional[str]
    tokens_json: List[object]
    risk_flags_json: List[object]
    confidence_score: Optional[Decimal]
    refusal_reason: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class ReportReasonCodeInput:
    """Structured valuation reason code."""

    id: UUID
    code: str
    label: str
    direction: str
    impact_amount: Optional[Decimal]
    impact_weight: Optional[Decimal]
    evidence_refs_json: List[object]
    explanation: str


@dataclass(frozen=True)
class ReportValuationInput:
    """Valuation snapshot used by report generation."""

    id: UUID
    status: str
    refusal_code: Optional[str]
    refusal_reason: Optional[str]
    estimated_value_min: Optional[Decimal]
    estimated_value_max: Optional[Decimal]
    estimated_value_point: Optional[Decimal]
    currency: str
    value_tier: str
    confidence_level: str
    algorithm_version: str
    input_fact_ids: List[UUID]
    input_signal_ids: List[UUID]
    created_at: datetime
    reason_codes: List[ReportReasonCodeInput]


@dataclass(frozen=True)
class ReportFactInput:
    """Verified fact input to keep report composition deterministic."""

    id: UUID
    fact_type: str
    fact_key: str
    fact_value_json: Dict[str, object]
    source_system: str
    source_url: Optional[str]
    observed_at: datetime


@dataclass(frozen=True)
class ReportSignalInput:
    """Derived signal input available for deterministic report sections."""

    id: UUID
    signal_type: str
    signal_key: str
    signal_value_json: Dict[str, object]
    confidence_score: Optional[Decimal]
    generated_at: datetime


@dataclass(frozen=True)
class ReportAIExplanationInput:
    """Validated narrative explanation that can be attached to the report."""

    id: UUID
    explanation_type: str
    model_name: str
    prompt_version: str
    text: str
    validation_status: str


@dataclass(frozen=True)
class ReportCompositionInput:
    """Complete deterministic input bundle for report generation."""

    organization_id: UUID
    domain: ReportDomainInput
    valuation: ReportValuationInput
    classification: Optional[ReportClassificationInput]
    auction: Optional[ReportAuctionInput]
    facts: List[ReportFactInput]
    signals: List[ReportSignalInput]
    validated_ai_explanations: List[ReportAIExplanationInput]
    report_template_version: str


@dataclass(frozen=True)
class GenerateAppraisalReportCommand:
    """Command for composing and storing an appraisal report."""

    organization_id: UUID
    domain_id: UUID
    valuation_run_id: UUID
    include_ai_explanations: bool
    report_template_version: str
    created_by_user_id: Optional[UUID]


@dataclass(frozen=True)
class AppraisalReportRecord:
    """Service-level stored appraisal report read model."""

    id: UUID
    organization_id: UUID
    domain_id: UUID
    valuation_run_id: UUID
    status: str
    report_template_version: str
    generated_at: datetime
    expires_at: Optional[datetime]
    created_by_user_id: Optional[UUID]
    report_json: AppraisalReportContract


class ReportInputNotFoundError(Exception):
    """Raised when report composition inputs cannot be loaded."""


class AppraisalReportRepositoryProtocol(Protocol):
    """Persistence boundary for report generation and reads."""

    def load_report_input(self, command: GenerateAppraisalReportCommand) -> Optional[ReportCompositionInput]:
        """Load the structured evidence required to build a report."""

    def create_report(
        self,
        *,
        organization_id: UUID,
        domain_id: UUID,
        valuation_run_id: UUID,
        status: str,
        report_template_version: str,
        report_json: Dict[str, Any],
        generated_at: datetime,
        created_by_user_id: Optional[UUID],
    ) -> AppraisalReportRecord:
        """Persist a generated report."""

    def get_report(self, report_id: UUID, organization_id: Optional[UUID]) -> Optional[AppraisalReportRecord]:
        """Read a stored report by id."""


class ReportService:
    """Application service for appraisal report composition and reads."""

    def __init__(self, repository: AppraisalReportRepositoryProtocol) -> None:
        self.repository = repository

    def generate_appraisal_report(self, command: GenerateAppraisalReportCommand) -> AppraisalReportRecord:
        """Compose and persist a reproducible appraisal report."""

        report_input = self.repository.load_report_input(command)
        if report_input is None:
            raise ReportInputNotFoundError(
                f"Unable to load report inputs for domain {command.domain_id} and valuation {command.valuation_run_id}."
            )

        generated_at = _utc_now()
        document = compose_appraisal_report(report_input, generated_at=generated_at)
        return self.repository.create_report(
            organization_id=command.organization_id,
            domain_id=command.domain_id,
            valuation_run_id=command.valuation_run_id,
            status=_status_for_valuation(report_input.valuation.status),
            report_template_version=command.report_template_version,
            report_json=_dump_model(document),
            generated_at=generated_at,
            created_by_user_id=command.created_by_user_id,
        )

    def get_appraisal_report(
        self,
        report_id: UUID,
        organization_id: Optional[UUID] = None,
    ) -> Optional[AppraisalReportRecord]:
        """Return a previously generated report."""

        return self.repository.get_report(report_id, organization_id)


def compose_appraisal_report(
    report_input: ReportCompositionInput,
    generated_at: Optional[datetime] = None,
) -> AppraisalReportContract:
    """Build the deterministic-first appraisal report JSON payload."""

    report_generated_at = generated_at or _utc_now()
    wholesale_range = _extract_wholesale_range(report_input.signals, report_input.valuation.currency)
    fair_market_range = _valuation_range(report_input.valuation)
    recommended_listing_price = _recommended_listing_price(report_input.valuation)
    minimum_acceptable_offer = _minimum_acceptable_offer(report_input.valuation)

    return AppraisalReportContract(
        schema_version="appraisal-report-v1",
        report_template_version=report_input.report_template_version,
        generated_at=report_generated_at,
        valuation_status=report_input.valuation.status,
        domain_header=DomainHeaderContract(
            fqdn=report_input.domain.fqdn,
            sld=report_input.domain.sld,
            tld=report_input.domain.tld,
            punycode_fqdn=report_input.domain.punycode_fqdn,
            unicode_fqdn=report_input.domain.unicode_fqdn,
            is_valid=report_input.domain.is_valid,
            auction_id=str(report_input.auction.id) if report_input.auction else None,
        ),
        classification=_build_classification(report_input.classification),
        recommended_listing_price=recommended_listing_price,
        fair_market_range=fair_market_range,
        confidence_level=report_input.valuation.confidence_level,
        whois_intelligence=_build_whois_intelligence(report_input.facts),
        tld_ecosystem_summary=_build_tld_ecosystem_summary(report_input.facts, report_input.signals),
        market_analysis_summary=_build_market_analysis(
            auction=report_input.auction,
            valuation=report_input.valuation,
            reason_codes=report_input.valuation.reason_codes,
            signals=report_input.signals,
            wholesale_range=wholesale_range,
        ),
        score_breakdown=_build_score_breakdown(report_input.valuation.reason_codes, report_input.signals),
        risks=_build_risks(report_input),
        final_verdict=_build_final_verdict(
            valuation=report_input.valuation,
            recommended_listing_price=recommended_listing_price,
        ),
        pricing_guidance=_build_pricing_guidance(
            valuation=report_input.valuation,
            recommended_listing_price=recommended_listing_price,
            fair_market_range=fair_market_range,
            wholesale_range=wholesale_range,
            minimum_acceptable_offer=minimum_acceptable_offer,
        ),
        supporting_facts=[
            FactSnapshotContract(
                fact_id=str(fact.id),
                fact_type=fact.fact_type,
                fact_key=fact.fact_key,
                source_system=fact.source_system,
                observed_at=fact.observed_at,
            )
            for fact in sorted(report_input.facts, key=lambda item: item.observed_at, reverse=True)
        ],
        derived_signals=[
            SignalSnapshotContract(
                signal_id=str(signal.id),
                signal_type=signal.signal_type,
                signal_key=signal.signal_key,
                confidence_score=_decimal_to_float(signal.confidence_score),
                generated_at=signal.generated_at,
            )
            for signal in sorted(report_input.signals, key=lambda item: item.generated_at, reverse=True)
        ],
        validated_ai_explanations=[
            AIExplanationSnippetContract(
                explanation_id=str(explanation.id),
                explanation_type=explanation.explanation_type,
                model_name=explanation.model_name,
                prompt_version=explanation.prompt_version,
                validation_status=explanation.validation_status,
                text=explanation.text,
            )
            for explanation in report_input.validated_ai_explanations
        ],
    )


def _build_classification(classification: Optional[ReportClassificationInput]) -> ClassificationContract:
    if classification is None:
        return ClassificationContract()
    return ClassificationContract(
        domain_type=classification.domain_type,
        business_category=classification.business_category,
        language_code=classification.language_code,
        confidence_score=_decimal_to_float(classification.confidence_score),
        risk_flags=[_normalize_dict(item) for item in classification.risk_flags_json],
        refusal_reason=classification.refusal_reason,
    )


def _build_whois_intelligence(facts: Sequence[ReportFactInput]) -> WhoisIntelligenceContract:
    registrar, registrar_ids = _extract_scalar_from_facts(facts, WHOIS_FIELD_ALIASES["registrar"])
    created_at, created_ids = _extract_datetime_from_facts(facts, WHOIS_FIELD_ALIASES["created_at"])
    updated_at, updated_ids = _extract_datetime_from_facts(facts, WHOIS_FIELD_ALIASES["updated_at"])
    expires_at, expires_ids = _extract_datetime_from_facts(facts, WHOIS_FIELD_ALIASES["expires_at"])
    status_labels, status_ids = _extract_list_from_facts(facts, WHOIS_FIELD_ALIASES["status_labels"])
    nameservers, nameserver_ids = _extract_list_from_facts(facts, WHOIS_FIELD_ALIASES["nameservers"])
    privacy_protected, privacy_ids = _extract_bool_from_facts(facts, WHOIS_FIELD_ALIASES["privacy_protected"])
    registrant_country, country_ids = _extract_scalar_from_facts(facts, WHOIS_FIELD_ALIASES["registrant_country"])

    used_ids = {
        *registrar_ids,
        *created_ids,
        *updated_ids,
        *expires_ids,
        *status_ids,
        *nameserver_ids,
        *privacy_ids,
        *country_ids,
    }
    if registrar or created_at or expires_at or status_labels or nameservers:
        status = "complete" if registrar and created_at and expires_at else "partial"
    else:
        status = "missing"

    return WhoisIntelligenceContract(
        status=status,
        registrar=registrar,
        created_at=created_at,
        updated_at=updated_at,
        expires_at=expires_at,
        status_labels=status_labels,
        nameservers=nameservers,
        privacy_protected=privacy_protected,
        registrant_country=registrant_country,
        source_fact_ids=sorted(used_ids),
    )


def _build_tld_ecosystem_summary(
    facts: Sequence[ReportFactInput],
    signals: Sequence[ReportSignalInput],
) -> TLDEcosystemSummaryContract:
    registered_extensions, registered_ids = _extract_list_from_facts(
        facts,
        TLD_FIELD_ALIASES["registered_extensions"],
    )
    active_extensions, active_ids = _extract_list_from_facts(
        facts,
        TLD_FIELD_ALIASES["active_website_extensions"],
    )
    parked_extensions, parked_ids = _extract_list_from_facts(
        facts,
        TLD_FIELD_ALIASES["parked_extensions"],
    )
    extension_count, count_ids = _extract_int_from_facts(facts, TLD_FIELD_ALIASES["extension_count"])
    narrative_flags = _extract_textual_signal_messages(signals, TLD_FIELD_ALIASES["narrative_flags"])

    refs = [
        EvidenceReferenceContract(kind="fact", ref_id=fact_id)
        for fact_id in sorted({*registered_ids, *active_ids, *parked_ids, *count_ids})
    ]
    status = "available" if registered_extensions or active_extensions or parked_extensions or extension_count else "missing"
    return TLDEcosystemSummaryContract(
        status=status,
        registered_extensions=registered_extensions,
        active_website_extensions=active_extensions,
        parked_extensions=parked_extensions,
        extension_count=extension_count,
        narrative_flags=narrative_flags,
        source_refs=refs,
    )


def _build_market_analysis(
    *,
    auction: Optional[ReportAuctionInput],
    valuation: ReportValuationInput,
    reason_codes: Sequence[ReportReasonCodeInput],
    signals: Sequence[ReportSignalInput],
    wholesale_range: Optional[ValueRangeContract],
) -> MarketAnalysisSummaryContract:
    retail_point = _range_midpoint(_valuation_range(valuation))
    wholesale_point = _range_midpoint(wholesale_range)
    current_bid = _money_from_decimal(auction.current_bid_amount, auction.currency) if auction else None

    supporting_reasons = [reason.label for reason in reason_codes if reason.direction == "positive"]
    limiting_reasons = [reason.label for reason in reason_codes if reason.direction == "negative"]

    return MarketAnalysisSummaryContract(
        auction_status=auction.status if auction else None,
        auction_type=auction.auction_type if auction else None,
        marketplace_code=auction.marketplace_code if auction else None,
        current_bid=current_bid,
        auction_end_at=auction.ends_at if auction else None,
        bid_count=auction.bid_count if auction else None,
        watchers_count=auction.watchers_count if auction else None,
        bid_to_estimated_wholesale_ratio=_money_ratio(auction.current_bid_amount if auction else None, wholesale_point),
        bid_to_estimated_retail_ratio=_money_ratio(auction.current_bid_amount if auction else None, retail_point),
        supporting_reasons=supporting_reasons,
        limiting_reasons=limiting_reasons,
        market_signals=_extract_textual_signal_messages(signals, MARKET_SIGNAL_KEYS),
    )


def _build_score_breakdown(
    reason_codes: Sequence[ReportReasonCodeInput],
    signals: Sequence[ReportSignalInput],
) -> ScoreBreakdownContract:
    score_map = {signal.signal_key: _extract_decimal_from_signal(signal) for signal in signals}
    components = [
        ScoreComponentContract(
            code=signal.signal_key,
            label=NUMERIC_SCORE_SIGNAL_KEYS[signal.signal_key],
            score=_decimal_to_float(score_map[signal.signal_key]),
            explanation=_extract_signal_message(signal),
        )
        for signal in signals
        if signal.signal_key in NUMERIC_SCORE_SIGNAL_KEYS
    ]
    components.extend(
        ScoreComponentContract(
            code=reason.code,
            label=reason.label,
            score=_decimal_to_float(reason.impact_weight),
            direction=reason.direction,
            explanation=reason.explanation,
        )
        for reason in reason_codes
    )
    return ScoreBreakdownContract(
        overall_investment_score=_decimal_to_float(score_map.get("investment_score")),
        liquidity_score=_decimal_to_float(score_map.get("liquidity_score")),
        brand_score=_decimal_to_float(score_map.get("brand_score")),
        risk_score=_decimal_to_float(score_map.get("risk_score")),
        components=components,
    )


def _build_risks(report_input: ReportCompositionInput) -> List[RiskContract]:
    risks: List[RiskContract] = []

    if report_input.classification is not None:
        for risk_flag in report_input.classification.risk_flags_json:
            risk = _normalize_dict(risk_flag)
            code = str(risk.get("code") or risk.get("flag") or "classification_risk")
            summary = str(risk.get("summary") or risk.get("label") or code.replace("_", " "))
            level = str(risk.get("level") or "warning")
            risks.append(
                RiskContract(
                    code=code,
                    level=level,
                    source="classification",
                    summary=summary,
                )
            )

    if report_input.valuation.refusal_code:
        risks.append(
            RiskContract(
                code=report_input.valuation.refusal_code,
                level="critical",
                source="valuation",
                summary=report_input.valuation.refusal_reason or report_input.valuation.refusal_code.replace("_", " "),
            )
        )

    risk_score = _signal_decimal(report_input.signals, "risk_score")
    if risk_score is not None and risk_score >= Decimal("0.50"):
        risks.append(
            RiskContract(
                code="elevated_risk_score",
                level="high",
                source="derived_signal",
                summary=f"Derived risk score is {risk_score.quantize(Decimal('0.01'))}.",
                evidence_refs=[EvidenceReferenceContract(kind="signal", ref_id=str(signal.id), label="risk_score") for signal in report_input.signals if signal.signal_key == "risk_score"],
            )
        )

    for fact in report_input.facts:
        combined_text = f"{fact.fact_type} {fact.fact_key} {_extract_signal_safe_text(fact.fact_value_json)}".lower()
        if "trademark" in combined_text or "udrp" in combined_text or "legal" in combined_text:
            risks.append(
                RiskContract(
                    code="legal_or_trademark_risk",
                    level="critical",
                    source="verified_fact",
                    summary="Verified evidence indicates legal or trademark review is required.",
                    evidence_refs=[EvidenceReferenceContract(kind="fact", ref_id=str(fact.id), label=fact.fact_key)],
                )
            )

    return _dedupe_risks(risks)


def _build_final_verdict(
    *,
    valuation: ReportValuationInput,
    recommended_listing_price: Optional[MoneyContract],
) -> FinalVerdictContract:
    if valuation.status == ValuationStatus.REFUSED.value:
        headline = "Valuation refused pending prerequisite or risk resolution."
        summary = valuation.refusal_reason or "A deterministic guardrail blocked valuation output."
        return FinalVerdictContract(
            status=valuation.status,
            headline=headline,
            summary=summary,
            value_tier=valuation.value_tier,
            pricing_posture="do_not_list",
            action="resolve_blocker",
            refusal_code=valuation.refusal_code,
            refusal_reason=valuation.refusal_reason,
        )

    if valuation.status == ValuationStatus.NEEDS_REVIEW.value:
        return FinalVerdictContract(
            status=valuation.status,
            headline="Manual review recommended before pricing or outreach.",
            summary="Structured inputs are available, but the valuation still requires analyst review.",
            value_tier=valuation.value_tier,
            pricing_posture="manual_review",
            action="review_inputs",
        )

    headline = "Deterministic valuation produced a listable pricing posture."
    summary = (
        f"Recommended BIN is {recommended_listing_price.amount} {recommended_listing_price.currency} "
        f"with {valuation.confidence_level} confidence."
        if recommended_listing_price is not None
        else "A fair-market range is available, but no point estimate was stored."
    )
    return FinalVerdictContract(
        status=valuation.status,
        headline=headline,
        summary=summary,
        value_tier=valuation.value_tier,
        pricing_posture="bin" if recommended_listing_price else "make_offer",
        action="list_or_watch",
    )


def _build_pricing_guidance(
    *,
    valuation: ReportValuationInput,
    recommended_listing_price: Optional[MoneyContract],
    fair_market_range: Optional[ValueRangeContract],
    wholesale_range: Optional[ValueRangeContract],
    minimum_acceptable_offer: Optional[MoneyContract],
) -> PricingGuidanceContract:
    notes: List[str] = []
    if wholesale_range is None:
        notes.append("No structured wholesale estimate was provided by upstream signals.")
    if valuation.status == ValuationStatus.REFUSED.value:
        notes.append("Do not publish pricing while valuation is in a refusal state.")
    elif valuation.status == ValuationStatus.NEEDS_REVIEW.value:
        notes.append("Treat all pricing as analyst-review only until manual review completes.")

    pricing_strategy = "do_not_list"
    if valuation.status == ValuationStatus.VALUED.value:
        pricing_strategy = "bin" if recommended_listing_price else "make_offer"
    elif valuation.status == ValuationStatus.NEEDS_REVIEW.value:
        pricing_strategy = "manual_review"

    return PricingGuidanceContract(
        pricing_strategy=pricing_strategy,
        estimated_retail_range=fair_market_range,
        estimated_wholesale_range=wholesale_range,
        bin_price=recommended_listing_price,
        minimum_acceptable_offer=minimum_acceptable_offer,
        listing_confidence=valuation.confidence_level,
        notes=notes,
    )


def _valuation_range(valuation: ReportValuationInput) -> Optional[ValueRangeContract]:
    if valuation.status != ValuationStatus.VALUED.value:
        return None
    if valuation.estimated_value_min is None or valuation.estimated_value_max is None:
        return None
    return ValueRangeContract(
        low=_format_money_amount(valuation.estimated_value_min),
        high=_format_money_amount(valuation.estimated_value_max),
        currency=valuation.currency,
    )


def _recommended_listing_price(valuation: ReportValuationInput) -> Optional[MoneyContract]:
    if valuation.status != ValuationStatus.VALUED.value:
        return None
    point_value = valuation.estimated_value_point
    if point_value is None and valuation.estimated_value_min is not None and valuation.estimated_value_max is not None:
        point_value = (valuation.estimated_value_min + valuation.estimated_value_max) / Decimal("2")
    return _money_from_decimal(point_value, valuation.currency)


def _minimum_acceptable_offer(valuation: ReportValuationInput) -> Optional[MoneyContract]:
    if valuation.status != ValuationStatus.VALUED.value or valuation.estimated_value_min is None:
        return None
    return _money_from_decimal(valuation.estimated_value_min, valuation.currency)


def _extract_wholesale_range(
    signals: Sequence[ReportSignalInput],
    currency: str,
) -> Optional[ValueRangeContract]:
    low = _signal_decimal_from_keys(signals, WHOLESALE_RANGE_LOW_KEYS)
    high = _signal_decimal_from_keys(signals, WHOLESALE_RANGE_HIGH_KEYS)
    point = _signal_decimal_from_keys(signals, WHOLESALE_SIGNAL_KEYS)

    if low is None and high is None and point is not None:
        low = point
        high = point
    if low is None or high is None:
        return None
    if low > high:
        low, high = high, low
    return ValueRangeContract(
        low=_format_money_amount(low),
        high=_format_money_amount(high),
        currency=currency,
    )


def _extract_scalar_from_facts(
    facts: Sequence[ReportFactInput],
    aliases: Iterable[str],
) -> tuple[Optional[str], List[str]]:
    alias_set = set(aliases)
    for fact in sorted(facts, key=lambda item: item.observed_at, reverse=True):
        match = _match_fact_values(fact, alias_set)
        if not match:
            continue
        for value in match:
            scalar = _coerce_scalar(value)
            if scalar is not None:
                return scalar, [str(fact.id)]
    return None, []


def _extract_datetime_from_facts(
    facts: Sequence[ReportFactInput],
    aliases: Iterable[str],
) -> tuple[Optional[datetime], List[str]]:
    value, source_ids = _extract_scalar_from_facts(facts, aliases)
    if value is None:
        return None, []
    return _parse_datetime(value), source_ids


def _extract_bool_from_facts(
    facts: Sequence[ReportFactInput],
    aliases: Iterable[str],
) -> tuple[Optional[bool], List[str]]:
    alias_set = set(aliases)
    for fact in sorted(facts, key=lambda item: item.observed_at, reverse=True):
        match = _match_fact_values(fact, alias_set)
        if not match:
            continue
        for value in match:
            if isinstance(value, bool):
                return value, [str(fact.id)]
            scalar = _coerce_scalar(value)
            if scalar is not None and scalar.lower() in {"true", "false"}:
                return scalar.lower() == "true", [str(fact.id)]
    return None, []


def _extract_int_from_facts(
    facts: Sequence[ReportFactInput],
    aliases: Iterable[str],
) -> tuple[Optional[int], List[str]]:
    value, source_ids = _extract_scalar_from_facts(facts, aliases)
    if value is None:
        return None, []
    try:
        return int(value), source_ids
    except ValueError:
        return None, []


def _extract_list_from_facts(
    facts: Sequence[ReportFactInput],
    aliases: Iterable[str],
) -> tuple[List[str], List[str]]:
    alias_set = set(aliases)
    values: List[str] = []
    source_ids: List[str] = []
    for fact in sorted(facts, key=lambda item: item.observed_at, reverse=True):
        match = _match_fact_values(fact, alias_set)
        if not match:
            continue
        source_ids.append(str(fact.id))
        for item in match:
            if isinstance(item, list):
                values.extend(_normalize_string_list(item))
            else:
                scalar = _coerce_scalar(item)
                if scalar is not None:
                    values.append(scalar)
    return _dedupe_preserve_order(values), _dedupe_preserve_order(source_ids)


def _extract_textual_signal_messages(
    signals: Sequence[ReportSignalInput],
    allowed_keys: Iterable[str],
) -> List[str]:
    allowed = set(allowed_keys)
    messages: List[str] = []
    for signal in sorted(signals, key=lambda item: item.generated_at, reverse=True):
        if signal.signal_key not in allowed:
            continue
        message = _extract_signal_message(signal)
        if message:
            messages.append(message)
    return _dedupe_preserve_order(messages)


def _extract_signal_message(signal: ReportSignalInput) -> Optional[str]:
    payload = signal.signal_value_json
    for key in ("summary", "label", "message", "band", "value"):
        value = payload.get(key)
        scalar = _coerce_scalar(value)
        if scalar:
            return scalar
    return None


def _extract_decimal_from_signal(signal: ReportSignalInput) -> Optional[Decimal]:
    return _decimal_from_payload(signal.signal_value_json)


def _signal_decimal(signals: Sequence[ReportSignalInput], key: str) -> Optional[Decimal]:
    return _signal_decimal_from_keys(signals, {key})


def _signal_decimal_from_keys(signals: Sequence[ReportSignalInput], keys: set[str]) -> Optional[Decimal]:
    for signal in sorted(signals, key=lambda item: item.generated_at, reverse=True):
        if signal.signal_key not in keys:
            continue
        decimal_value = _extract_decimal_from_signal(signal)
        if decimal_value is not None:
            return decimal_value
    return None


def _match_fact_values(fact: ReportFactInput, aliases: set[str]) -> List[object]:
    matches: List[object] = []
    if fact.fact_key in aliases:
        matches.append(_extract_preferred_value(fact.fact_value_json, fact.fact_key))
    if fact.fact_type in aliases:
        matches.append(_extract_preferred_value(fact.fact_value_json))
    for key, value in fact.fact_value_json.items():
        if key in aliases:
            matches.append(value)
    return [match for match in matches if match is not None]


def _extract_preferred_value(payload: Dict[str, object], preferred_key: Optional[str] = None) -> Optional[object]:
    if preferred_key is not None and preferred_key in payload:
        return payload.get(preferred_key)
    for key in ("value", "values", "amount", "text", "label", "name"):
        if key in payload:
            return payload.get(key)
    if len(payload) == 1:
        return next(iter(payload.values()))
    return None


def _decimal_from_payload(payload: Dict[str, object]) -> Optional[Decimal]:
    for key in ("score", "value", "amount", "point", "estimate"):
        value = payload.get(key)
        decimal_value = _coerce_decimal(value)
        if decimal_value is not None:
            return decimal_value
    for value in payload.values():
        decimal_value = _coerce_decimal(value)
        if decimal_value is not None:
            return decimal_value
    return None


def _coerce_decimal(value: object) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            return None
    return None


def _coerce_scalar(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, str):
        return value
    return None


def _parse_datetime(value: str) -> Optional[datetime]:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _money_from_decimal(amount: Optional[Decimal], currency: Optional[str]) -> Optional[MoneyContract]:
    if amount is None or not currency:
        return None
    return MoneyContract(amount=_format_money_amount(amount), currency=currency)


def _format_money_amount(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _money_ratio(numerator: Optional[Decimal], denominator: Optional[Decimal]) -> Optional[float]:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    ratio = (numerator / denominator).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return float(ratio)


def _range_midpoint(value_range: Optional[ValueRangeContract]) -> Optional[Decimal]:
    if value_range is None:
        return None
    return (Decimal(value_range.low) + Decimal(value_range.high)) / Decimal("2")


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _normalize_dict(value: object) -> Dict[str, object]:
    return value if isinstance(value, dict) else {"value": value}


def _normalize_string_list(values: Iterable[object]) -> List[str]:
    normalized: List[str] = []
    for value in values:
        scalar = _coerce_scalar(value)
        if scalar is not None:
            normalized.append(scalar)
    return normalized


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _extract_signal_safe_text(payload: Dict[str, object]) -> str:
    values = [str(value) for value in payload.values()]
    return " ".join(values)


def _dedupe_risks(risks: Sequence[RiskContract]) -> List[RiskContract]:
    seen: set[tuple[str, str, str]] = set()
    deduped: List[RiskContract] = []
    for risk in risks:
        key = (risk.code, risk.source, risk.summary)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(risk)
    return deduped


def _status_for_valuation(valuation_status: str) -> str:
    if valuation_status == ValuationStatus.REFUSED.value:
        return AppraisalReportStatus.REFUSED.value
    if valuation_status == ValuationStatus.NEEDS_REVIEW.value:
        return AppraisalReportStatus.NEEDS_REVIEW.value
    return AppraisalReportStatus.GENERATED.value


def _dump_model(model: AppraisalReportContract) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
