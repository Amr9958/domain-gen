"""Valuation engine unit tests and example scenarios."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import uuid4

from domain_intel.core.enums import DomainType, ValuationRefusalCode, ValuationStatus, ValueTier
from domain_intel.services.valuation_service import ValuationService
from domain_intel.valuation.engine import RuleBasedValuationEngine
from domain_intel.valuation.interfaces import ValuationProviderError
from domain_intel.valuation.models import (
    ClassificationSnapshot,
    ComparableSale,
    ComparableSalesSupport,
    DomainRecord,
    DomainValuationRequest,
    HistoricalSignals,
    MarketDemandSignals,
    RiskSignals,
    TldEcosystemSignals,
)


def test_weight_profiles_sum_to_one_hundred() -> None:
    engine = RuleBasedValuationEngine()

    exact_weights = engine.describe_weights(DomainType.EXACT_MATCH)
    brandable_weights = engine.describe_weights(DomainType.BRANDABLE)

    assert round(sum(exact_weights.values()), 6) == 100.0
    assert round(sum(brandable_weights.values()), 6) == 100.0
    assert brandable_weights != exact_weights


def test_missing_classification_returns_refusal() -> None:
    result = ValuationService().value_domain(
        DomainValuationRequest(
            domain=make_domain("example.com"),
            classification=None,
        )
    )

    assert result.status is ValuationStatus.REFUSED
    assert result.refusal_code is ValuationRefusalCode.MISSING_CLASSIFICATION
    assert result.value_tier is ValueTier.REFUSAL


def test_thin_data_returns_refusal() -> None:
    result = ValuationService().value_domain(
        DomainValuationRequest(
            domain=make_domain("cloudstorage.com"),
            classification=make_classification(
                domain_type=DomainType.EXACT_MATCH,
                confidence_score=0.90,
                tokens=("cloud", "storage"),
                business_category="software",
            ),
        )
    )

    assert result.status is ValuationStatus.REFUSED
    assert result.refusal_code is ValuationRefusalCode.INSUFFICIENT_EVIDENCE


def test_high_legal_risk_returns_refusal() -> None:
    result = ValuationService().value_domain(
        DomainValuationRequest(
            domain=make_domain("brandshield.com"),
            classification=make_classification(
                domain_type=DomainType.BRANDABLE,
                confidence_score=0.82,
                tokens=("brandshield",),
                risk_flags=("trademark_exact",),
            ),
            market_signals=MarketDemandSignals(commercial_intent_score=0.50),
            ecosystem_signals=TldEcosystemSignals(tld="com", registry_strength_score=0.90),
        )
    )

    assert result.status is ValuationStatus.REFUSED
    assert result.refusal_code is ValuationRefusalCode.LEGAL_OR_TRADEMARK_RISK


def test_provider_failure_is_translated_to_refusal() -> None:
    service = ValuationService(
        comparable_sales_provider=FailingComparableProvider(),
        ecosystem_signal_provider=StaticEcosystemProvider(TldEcosystemSignals(tld="com", registry_strength_score=0.90)),
    )

    result = service.value_domain(
        DomainValuationRequest(
            domain=make_domain("zentra.com"),
            classification=make_classification(
                domain_type=DomainType.BRANDABLE,
                confidence_score=0.84,
                tokens=("zentra",),
            ),
            historical_signals=HistoricalSignals(years_since_first_seen=8),
            market_signals=MarketDemandSignals(commercial_intent_score=0.55),
        )
    )

    assert result.status is ValuationStatus.REFUSED
    assert result.refusal_code is ValuationRefusalCode.PROVIDER_FAILURE


def test_example_valuations_are_ranked_and_explainable() -> None:
    service = ValuationService()

    strong_exact = service.value_domain(strong_exact_match_request())
    geo_service = service.value_domain(geo_service_request())
    short_brandable = service.value_domain(short_brandable_request())
    weak_awkward = service.value_domain(weak_awkward_request())

    assert strong_exact.status is ValuationStatus.VALUED
    assert strong_exact.score is not None and strong_exact.score >= 80
    assert strong_exact.value_tier in {ValueTier.HIGH, ValueTier.PREMIUM}
    assert strong_exact.wholesale_estimate is not None
    assert strong_exact.retail_estimate is not None
    assert strong_exact.reason_codes
    assert len(strong_exact.score_breakdown) == 14

    assert geo_service.status is ValuationStatus.VALUED
    assert geo_service.score is not None and 65 <= geo_service.score < strong_exact.score
    assert geo_service.retail_estimate is not None

    assert short_brandable.status in {ValuationStatus.VALUED, ValuationStatus.NEEDS_REVIEW}
    assert short_brandable.score is not None and 58 <= short_brandable.score < strong_exact.score
    assert short_brandable.retail_estimate is not None

    assert weak_awkward.status in {ValuationStatus.VALUED, ValuationStatus.NEEDS_REVIEW}
    assert weak_awkward.score is not None and weak_awkward.score < 55
    assert weak_awkward.value_tier is ValueTier.LOW
    assert weak_awkward.retail_estimate is not None

    assert strong_exact.retail_estimate.point_amount > geo_service.retail_estimate.point_amount
    assert geo_service.retail_estimate.point_amount > short_brandable.retail_estimate.point_amount
    assert short_brandable.retail_estimate.point_amount > weak_awkward.retail_estimate.point_amount


class StaticEcosystemProvider:
    def __init__(self, signals: TldEcosystemSignals) -> None:
        self.signals = signals

    def lookup_signals(self, query) -> TldEcosystemSignals:
        return self.signals


class FailingComparableProvider:
    def lookup_support(self, query) -> ComparableSalesSupport:
        raise ValuationProviderError("comparable source unavailable")


def strong_exact_match_request() -> DomainValuationRequest:
    return DomainValuationRequest(
        domain=make_domain("cloudstorage.com"),
        classification=make_classification(
            domain_type=DomainType.EXACT_MATCH,
            confidence_score=0.91,
            tokens=("cloud", "storage"),
            business_category="software",
        ),
        historical_signals=HistoricalSignals(
            years_since_first_seen=17,
            active_website_years=6,
            archive_snapshot_count=24,
            website_resolves=True,
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=0.92,
            active_business_score=0.88,
            active_business_count=36,
            search_demand_score=0.85,
            trend_score=0.42,
            liquidity_score=0.78,
        ),
        comparable_support=ComparableSalesSupport(
            sales=(
                sale("cloudstack.com", "12000", 0.88),
                sale("cloudsuite.com", "14500", 0.84),
                sale("storagedirect.com", "9600", 0.76),
            ),
        ),
        ecosystem_signals=TldEcosystemSignals(
            tld="com",
            registry_strength_score=0.92,
            aftermarket_liquidity_score=0.86,
            end_user_adoption_score=0.90,
            upgrade_target_score=0.84,
            registered_extension_count=18,
        ),
    )


def geo_service_request() -> DomainValuationRequest:
    return DomainValuationRequest(
        domain=make_domain("austinplumbing.com"),
        classification=make_classification(
            domain_type=DomainType.GEO,
            confidence_score=0.88,
            tokens=("austin", "plumbing"),
            business_category="home_services",
        ),
        historical_signals=HistoricalSignals(
            years_since_first_seen=12,
            active_website_years=4,
            archive_snapshot_count=11,
            website_resolves=True,
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=0.80,
            active_business_score=0.74,
            active_business_count=28,
            search_demand_score=0.72,
            trend_score=0.28,
            liquidity_score=0.60,
        ),
        comparable_support=ComparableSalesSupport(
            sales=(
                sale("dallasplumbing.com", "4100", 0.82),
                sale("houstonplumbing.com", "3600", 0.80),
                sale("tulsaplumbing.com", "2950", 0.70),
            ),
        ),
        ecosystem_signals=TldEcosystemSignals(
            tld="com",
            registry_strength_score=0.90,
            aftermarket_liquidity_score=0.78,
            end_user_adoption_score=0.85,
            upgrade_target_score=0.76,
            registered_extension_count=9,
        ),
    )


def short_brandable_request() -> DomainValuationRequest:
    return DomainValuationRequest(
        domain=make_domain("zentra.com"),
        classification=make_classification(
            domain_type=DomainType.BRANDABLE,
            confidence_score=0.84,
            tokens=("zentra",),
            business_category="software",
        ),
        historical_signals=HistoricalSignals(
            years_since_first_seen=9,
            active_website_years=2,
            archive_snapshot_count=7,
            website_resolves=True,
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=0.58,
            active_business_score=0.50,
            active_business_count=9,
            search_demand_score=0.46,
            trend_score=0.35,
            liquidity_score=0.66,
        ),
        comparable_support=ComparableSalesSupport(
            sales=(
                sale("ventra.com", "3200", 0.78),
                sale("zentro.com", "2800", 0.76),
                sale("nexra.com", "2400", 0.64),
            ),
        ),
        ecosystem_signals=TldEcosystemSignals(
            tld="com",
            registry_strength_score=0.89,
            aftermarket_liquidity_score=0.72,
            end_user_adoption_score=0.79,
            upgrade_target_score=0.60,
            registered_extension_count=4,
        ),
    )


def weak_awkward_request() -> DomainValuationRequest:
    return DomainValuationRequest(
        domain=make_domain("cucumberfragility.net"),
        classification=make_classification(
            domain_type=DomainType.KEYWORD_PHRASE,
            confidence_score=0.77,
            tokens=("cucumber", "fragility"),
            business_category="unknown",
        ),
        historical_signals=HistoricalSignals(
            years_since_first_seen=1,
            active_website_years=0,
            archive_snapshot_count=1,
            website_resolves=False,
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=0.12,
            active_business_score=0.06,
            active_business_count=0,
            search_demand_score=0.08,
            trend_score=0.04,
            liquidity_score=0.10,
        ),
        risk_signals=RiskSignals(typo_confusion_score=0.10),
        comparable_support=ComparableSalesSupport(),
        ecosystem_signals=TldEcosystemSignals(
            tld="net",
            registry_strength_score=0.30,
            aftermarket_liquidity_score=0.16,
            end_user_adoption_score=0.20,
            upgrade_target_score=0.10,
            registered_extension_count=0,
        ),
    )


def make_domain(fqdn: str) -> DomainRecord:
    sld, tld = fqdn.split(".", 1)
    return DomainRecord(id=uuid4(), fqdn=fqdn, sld=sld, tld=tld, is_valid=True)


def make_classification(
    domain_type: DomainType,
    confidence_score: float,
    tokens: tuple[str, ...],
    business_category: Optional[str] = None,
    risk_flags: tuple[str, ...] = tuple(),
) -> ClassificationSnapshot:
    return ClassificationSnapshot(
        classification_result_id=uuid4(),
        domain_type=domain_type,
        confidence_score=confidence_score,
        business_category=business_category,
        tokens=tokens,
        risk_flags=risk_flags,
    )


def sale(domain: str, amount: str, similarity: float) -> ComparableSale:
    return ComparableSale(
        sale_id=str(uuid4()),
        domain=domain,
        price=Decimal(amount),
        currency="USD",
        similarity_score=similarity,
    )
