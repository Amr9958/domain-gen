"""FastAPI route tests for listing queries."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest


pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from domain_intel.api.dependencies import get_auction_service, get_health_service
from domain_intel.main import create_app
from domain_intel.services.auction_service import (
    AuctionListingPage,
    AuctionListingRecord,
    DomainSummary,
    MarketplaceSummary,
    MoneyValue,
)
from domain_intel.services.health_service import HealthCheckResult


class FakeAuctionService:
    def __init__(self) -> None:
        self.filters = None

    def list_listings(self, filters):
        self.filters = filters
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        item = AuctionListingRecord(
            id=uuid4(),
            source_item_id="source-1",
            source_url="https://example.test/source-1",
            auction_type="expired",
            status="open",
            starts_at=None,
            ends_at=now,
            current_bid=MoneyValue(amount="125.00", currency="USD"),
            min_bid=MoneyValue(amount="69.00", currency="USD"),
            bid_count=3,
            watchers_count=None,
            first_seen_at=now,
            last_seen_at=now,
            closed_at=None,
            marketplace=MarketplaceSummary(id=uuid4(), code="dynadot", display_name="Dynadot"),
            domain=DomainSummary(
                id=uuid4(),
                fqdn="example.com",
                sld="example",
                tld="com",
                punycode_fqdn="example.com",
                unicode_fqdn="example.com",
                is_valid=True,
            ),
        )
        return AuctionListingPage(items=[item], total=1, limit=filters.limit, offset=filters.offset)


class FakeHealthService:
    def check(self) -> HealthCheckResult:
        return HealthCheckResult(status="ok", database="ok")


def test_list_auctions_passes_supported_filters_to_service() -> None:
    fake_service = FakeAuctionService()
    app = create_app()
    app.dependency_overrides[get_auction_service] = lambda: fake_service
    client = TestClient(app)

    response = client.get(
        "/v1/auctions",
        params={
            "source": "dynadot",
            "tld": ".COM",
            "closes_after": "2026-04-23T00:00:00Z",
            "closes_before": "2026-04-24T00:00:00Z",
            "min_price": "25.00",
            "max_price": "500.00",
            "status": "open",
            "limit": "25",
            "offset": "5",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["current_bid"] == {"amount": "125.00", "currency": "USD"}
    assert fake_service.filters.source == "dynadot"
    assert fake_service.filters.normalized_tld == "com"
    assert fake_service.filters.min_price == Decimal("25.00")
    assert fake_service.filters.max_price == Decimal("500.00")
    assert fake_service.filters.limit == 25
    assert fake_service.filters.offset == 5


def test_health_endpoint_uses_health_service_dependency() -> None:
    app = create_app()
    app.dependency_overrides[get_health_service] = lambda: FakeHealthService()
    client = TestClient(app)

    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
