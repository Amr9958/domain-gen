"""FastAPI route tests for report and investor workflow endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest


pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from domain_intel.api.dependencies import (
    get_alert_service,
    get_opportunity_service,
    get_report_service,
    get_saved_search_service,
    get_watchlist_service,
)
from domain_intel.contracts.appraisal import (
    AppraisalReportContract,
    ClassificationContract,
    DomainHeaderContract,
    FinalVerdictContract,
    MarketAnalysisSummaryContract,
    PricingGuidanceContract,
    ScoreBreakdownContract,
    TLDEcosystemSummaryContract,
    ValueRangeContract,
    WhoisIntelligenceContract,
)
from domain_intel.main import create_app
from domain_intel.services.alert_service import AlertRuleRecord
from domain_intel.services.opportunity_service import (
    UndervaluedAuctionPage,
    UndervaluedAuctionRecord,
    ValueRangeValue,
)
from domain_intel.services.report_service import AppraisalReportRecord
from domain_intel.services.saved_search_service import (
    SavedSearchCommand,
    SavedSearchListResult,
    SavedSearchMutationResult,
    SavedSearchRecord,
    SavedSearchService,
    SavedSearchServiceError,
)
from domain_intel.services.shared_types import MoneyValue
from domain_intel.services.watchlist_service import WatchlistItemRecord, WatchlistRecord


def test_report_routes_generate_and_read() -> None:
    fake_service = FakeReportService()
    app = create_app()
    app.dependency_overrides[get_report_service] = lambda: fake_service
    client = TestClient(app)

    generate_response = client.post(
        "/v1/reports/appraisals",
        json={
            "organization_id": str(fake_service.record.organization_id),
            "domain_id": str(fake_service.record.domain_id),
            "valuation_run_id": str(fake_service.record.valuation_run_id),
            "include_ai_explanations": True,
            "report_template_version": "appraisal-v1",
            "created_by_user_id": str(fake_service.record.created_by_user_id),
        },
    )
    get_response = client.get(
        f"/v1/reports/appraisals/{fake_service.record.id}",
        params={"organization_id": str(fake_service.record.organization_id)},
    )

    assert generate_response.status_code == 200
    assert get_response.status_code == 200
    assert generate_response.json()["report_json"]["final_verdict"]["status"] == "valued"
    assert get_response.json()["report_json"]["recommended_listing_price"]["amount"] == "2750.00"


def test_watchlist_alert_and_saved_search_routes() -> None:
    fake_watchlist_service = FakeWatchlistService()
    fake_alert_service = FakeAlertService()
    fake_saved_search_service = FakeSavedSearchService()
    app = create_app()
    app.dependency_overrides[get_watchlist_service] = lambda: fake_watchlist_service
    app.dependency_overrides[get_alert_service] = lambda: fake_alert_service
    app.dependency_overrides[get_saved_search_service] = lambda: fake_saved_search_service
    client = TestClient(app)

    create_watchlist = client.post(
        "/v1/watchlists",
        json={
            "organization_id": str(fake_watchlist_service.watchlist.organization_id),
            "owner_user_id": str(fake_watchlist_service.watchlist.owner_user_id),
            "name": "Priority .coms",
            "visibility": "private",
        },
    )
    add_item = client.post(
        f"/v1/watchlists/{fake_watchlist_service.watchlist.id}/items",
        json={
            "domain_id": str(uuid4()),
            "auction_id": str(uuid4()),
            "created_by_user_id": str(fake_watchlist_service.watchlist.owner_user_id),
            "notes": "Track before close.",
        },
    )
    alert_rule = client.post(
        "/v1/alert-rules",
        json={
            "organization_id": str(fake_watchlist_service.watchlist.organization_id),
            "watchlist_id": str(fake_watchlist_service.watchlist.id),
            "rule_type": "price_below_threshold",
            "is_enabled": True,
            "threshold_json": {"amount": "500.00", "currency": "USD"},
            "channel_config_json": {"channels": ["email"]},
        },
    )
    saved_search = client.post(
        "/v1/saved-searches",
        json={
            "organization_id": str(fake_watchlist_service.watchlist.organization_id),
            "owner_user_id": str(fake_watchlist_service.watchlist.owner_user_id),
            "name": "Closing .com bargains",
            "search_scope": "undervalued_auctions",
            "filters_json": {"tld": "com", "source": "dynadot"},
            "sort_json": {"field": "ends_at", "direction": "asc"},
        },
    )

    assert create_watchlist.status_code == 200
    assert add_item.status_code == 200
    assert add_item.json()["created"] is True
    assert alert_rule.status_code == 200
    assert alert_rule.json()["rule_type"] == "price_below_threshold"
    assert saved_search.status_code == 200
    assert saved_search.json()["supported"] is False
    assert saved_search.json()["errors"][0]["code"] == "schema_contract_mismatch"


def test_undervalued_auctions_route_returns_dashboard_shape() -> None:
    fake_service = FakeOpportunityService()
    app = create_app()
    app.dependency_overrides[get_opportunity_service] = lambda: fake_service
    client = TestClient(app)

    response = client.get(
        "/v1/opportunities/undervalued-auctions",
        params={
            "source": "dynadot",
            "tld": ".com",
            "min_confidence_level": "medium",
            "max_risk_score": "0.25",
            "max_bid_to_wholesale_ratio": "1.00",
            "max_bid_to_retail_ratio": "0.35",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["status"] == "candidate"
    assert fake_service.query.policy.max_risk_score == Decimal("0.25")
    assert fake_service.query.source == "dynadot"


class FakeReportService:
    def __init__(self) -> None:
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        self.record = AppraisalReportRecord(
            id=uuid4(),
            organization_id=uuid4(),
            domain_id=uuid4(),
            valuation_run_id=uuid4(),
            status="generated",
            report_template_version="appraisal-v1",
            generated_at=now,
            expires_at=None,
            created_by_user_id=uuid4(),
            report_json=AppraisalReportContract(
                schema_version="appraisal-report-v1",
                report_template_version="appraisal-v1",
                generated_at=now,
                valuation_status="valued",
                domain_header=DomainHeaderContract(
                    fqdn="atlasai.com",
                    sld="atlasai",
                    tld="com",
                    punycode_fqdn="atlasai.com",
                    unicode_fqdn="atlasai.com",
                    is_valid=True,
                ),
                classification=ClassificationContract(domain_type="brandable", confidence_score=0.9),
                recommended_listing_price={"amount": "2750.00", "currency": "USD"},
                fair_market_range=ValueRangeContract(low="2000.00", high="3500.00", currency="USD"),
                confidence_level="high",
                whois_intelligence=WhoisIntelligenceContract(status="partial", registrar="Example Registrar"),
                tld_ecosystem_summary=TLDEcosystemSummaryContract(status="available"),
                market_analysis_summary=MarketAnalysisSummaryContract(marketplace_code="dynadot"),
                score_breakdown=ScoreBreakdownContract(overall_investment_score=0.72),
                risks=[],
                final_verdict=FinalVerdictContract(
                    status="valued",
                    headline="Valued",
                    summary="Structured valuation available.",
                    value_tier="meaningful",
                    pricing_posture="bin",
                    action="list_or_watch",
                ),
                pricing_guidance=PricingGuidanceContract(
                    pricing_strategy="bin",
                    estimated_retail_range=ValueRangeContract(low="2000.00", high="3500.00", currency="USD"),
                    bin_price={"amount": "2750.00", "currency": "USD"},
                    minimum_acceptable_offer={"amount": "2000.00", "currency": "USD"},
                    listing_confidence="high",
                ),
            ),
        )

    def generate_appraisal_report(self, command):
        return self.record

    def get_appraisal_report(self, report_id, organization_id=None):
        return self.record if report_id == self.record.id else None


class FakeWatchlistService:
    def __init__(self) -> None:
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        self.watchlist = WatchlistRecord(
            id=uuid4(),
            organization_id=uuid4(),
            owner_user_id=uuid4(),
            name="Priority .coms",
            visibility="private",
            created_at=now,
            updated_at=now,
            deleted_at=None,
            items=[],
        )

    def list_watchlists(self, organization_id, owner_user_id=None):
        return [self.watchlist]

    def create_watchlist(self, command):
        return self.watchlist

    def add_item(self, command):
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        return WatchlistItemRecord(
            id=uuid4(),
            watchlist_id=command.watchlist_id,
            domain_id=command.domain_id,
            auction_id=command.auction_id,
            notes=command.notes,
            created_at=now,
            created_by_user_id=command.created_by_user_id,
        )

    def remove_item(self, command):
        return True


class FakeAlertService:
    def create_rule(self, command):
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        return AlertRuleRecord(
            id=uuid4(),
            organization_id=command.organization_id,
            watchlist_id=command.watchlist_id,
            rule_type=command.rule_type,
            is_enabled=command.is_enabled,
            threshold_json=command.threshold_json,
            channel_config_json=command.channel_config_json,
            created_at=now,
            updated_at=now,
        )


class FakeSavedSearchService(SavedSearchService):
    def create_saved_search(self, command: SavedSearchCommand) -> SavedSearchMutationResult:
        return SavedSearchMutationResult(
            supported=False,
            saved_search=SavedSearchRecord(
                id=None,
                organization_id=command.organization_id,
                owner_user_id=command.owner_user_id,
                name=command.name,
                search_scope=command.search_scope,
                filters_json=command.filters_json,
                sort_json=command.sort_json,
            ),
            errors=[
                SavedSearchServiceError(
                    code="schema_contract_mismatch",
                    message="Saved-search persistence is not available in the approved shared schema.",
                    details={"required_patch": "saved_searches_table"},
                )
            ],
        )

    def list_saved_searches(self, organization_id, owner_user_id) -> SavedSearchListResult:
        return SavedSearchListResult(supported=False, items=[], errors=[])


class FakeOpportunityService:
    def __init__(self) -> None:
        self.query = None

    def list_undervalued_auctions(self, query):
        self.query = query
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        item = UndervaluedAuctionRecord(
            auction_id=uuid4(),
            domain_id=uuid4(),
            fqdn="atlasai.com",
            marketplace_code="dynadot",
            auction_type="expired",
            auction_status="open",
            ends_at=now,
            current_bid=MoneyValue(amount="800.00", currency="USD"),
            estimated_wholesale_range=ValueRangeValue(low="900.00", high="1100.00", currency="USD"),
            estimated_retail_range=ValueRangeValue(low="2500.00", high="3500.00", currency="USD"),
            bid_to_estimated_wholesale_ratio="0.8000",
            bid_to_estimated_retail_ratio="0.2667",
            confidence_level="high",
            risk_score="0.20",
            risk_flags=[],
            status="candidate",
            reasons=["Current bid sits below configured wholesale and retail thresholds."],
        )
        return UndervaluedAuctionPage(items=[item], total=1, limit=query.limit, offset=query.offset)
