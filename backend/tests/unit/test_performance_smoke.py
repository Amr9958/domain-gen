"""Local performance smoke checks for backend critical paths."""

from __future__ import annotations

from decimal import Decimal
import time
from uuid import uuid4

import pytest

from domain_intel.core.enums import DomainType, ValuationStatus
from domain_intel.services.valuation_service import ValuationService
from domain_intel.valuation.models import (
    ClassificationSnapshot,
    ComparableSale,
    ComparableSalesSupport,
    DomainRecord,
    DomainValuationRequest,
    HistoricalSignals,
    MarketDemandSignals,
    TldEcosystemSignals,
)


@pytest.mark.performance
def test_rule_based_valuation_performance_smoke() -> None:
    service = ValuationService()
    requests = [_valuation_request(index) for index in range(25)]

    start = time.perf_counter()
    results = [service.value_domain(request) for request in requests]
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"25 in-memory valuations took {elapsed:.3f}s; expected below 1s"
    assert all(result.status is ValuationStatus.VALUED for result in results)
    assert all(result.reason_codes for result in results)


def _valuation_request(index: int) -> DomainValuationRequest:
    return DomainValuationRequest(
        domain=DomainRecord(
            id=uuid4(),
            fqdn=f"cloudstack{index}.com",
            sld=f"cloudstack{index}",
            tld="com",
            is_valid=True,
        ),
        classification=ClassificationSnapshot(
            classification_result_id=uuid4(),
            domain_type=DomainType.EXACT_MATCH,
            confidence_score=0.91,
            business_category="software",
            tokens=("cloud", "stack"),
            risk_flags=(),
        ),
        historical_signals=HistoricalSignals(
            years_since_first_seen=12,
            active_website_years=5,
            archive_snapshot_count=18,
            website_resolves=True,
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=0.86,
            active_business_score=0.80,
            active_business_count=30,
            search_demand_score=0.78,
            trend_score=0.40,
            liquidity_score=0.72,
        ),
        comparable_support=ComparableSalesSupport(
            sales=(
                _sale("cloudstack.com", "12000", 0.88),
                _sale("cloudsuite.com", "9000", 0.80),
            ),
        ),
        ecosystem_signals=TldEcosystemSignals(
            tld="com",
            registry_strength_score=0.92,
            aftermarket_liquidity_score=0.86,
            end_user_adoption_score=0.90,
            upgrade_target_score=0.84,
            registered_extension_count=14,
        ),
    )


def _sale(domain: str, amount: str, similarity: float) -> ComparableSale:
    return ComparableSale(
        sale_id=str(uuid4()),
        domain=domain,
        price=Decimal(amount),
        currency="USD",
        similarity_score=similarity,
    )
