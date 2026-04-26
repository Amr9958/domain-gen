"""Auction service unit tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest


pytest.importorskip("sqlalchemy")

from domain_intel.core.enums import AuctionStatus, AuctionType
from domain_intel.repositories.auction_repository import AuctionQueryFilters
from domain_intel.services.auction_service import AuctionService


def test_query_filters_normalize_tld_without_mutating_input() -> None:
    filters = AuctionQueryFilters(tld=".COM")

    assert filters.tld == ".COM"
    assert filters.normalized_tld == "com"


def test_auction_service_returns_money_only_when_currency_is_verified() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    marketplace = SimpleNamespace(id=uuid4(), code="dynadot", display_name="Dynadot")
    domain = SimpleNamespace(
        id=uuid4(),
        fqdn="example.com",
        sld="example",
        tld="com",
        punycode_fqdn="example.com",
        unicode_fqdn="example.com",
        is_valid=True,
    )
    auction = SimpleNamespace(
        id=uuid4(),
        source_item_id="source-1",
        source_url="https://example.test/source-1",
        auction_type=AuctionType.EXPIRED,
        status=AuctionStatus.OPEN,
        starts_at=None,
        ends_at=now,
        current_bid_amount=Decimal("125"),
        min_bid_amount=Decimal("69.00"),
        currency=None,
        bid_count=3,
        watchers_count=None,
        first_seen_at=now,
        last_seen_at=now,
        closed_at=None,
        marketplace=marketplace,
        domain=domain,
    )

    service = AuctionService(repository=SimpleNamespace())
    record = service._to_record(auction)

    assert record.current_bid is None
    assert record.min_bid is None
