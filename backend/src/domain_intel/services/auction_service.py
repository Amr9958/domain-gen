"""Auction listing service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from domain_intel.db.models import Auction
from domain_intel.repositories.auction_repository import AuctionQueryFilters, AuctionRepository
from domain_intel.services.shared_types import MoneyValue


@dataclass(frozen=True)
class MarketplaceSummary:
    """Marketplace summary included on listing reads."""

    id: UUID
    code: str
    display_name: str


@dataclass(frozen=True)
class DomainSummary:
    """Canonical domain summary included on listing reads."""

    id: UUID
    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: Optional[str]
    is_valid: bool


@dataclass(frozen=True)
class AuctionListingRecord:
    """Service-level read model for an auction listing."""

    id: UUID
    source_item_id: str
    source_url: Optional[str]
    auction_type: str
    status: str
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    current_bid: Optional[MoneyValue]
    min_bid: Optional[MoneyValue]
    bid_count: Optional[int]
    watchers_count: Optional[int]
    first_seen_at: datetime
    last_seen_at: datetime
    closed_at: Optional[datetime]
    marketplace: MarketplaceSummary
    domain: DomainSummary


@dataclass(frozen=True)
class AuctionListingPage:
    """Paginated auction listing result."""

    items: List[AuctionListingRecord]
    total: int
    limit: int
    offset: int


class AuctionService:
    """Application service for normalized auction listing reads."""

    def __init__(self, repository: AuctionRepository) -> None:
        self.repository = repository

    def list_listings(self, filters: AuctionQueryFilters) -> AuctionListingPage:
        """List normalized auctions without source-specific parsing."""

        auctions, total = self.repository.list_listings(filters)
        return AuctionListingPage(
            items=[self._to_record(auction) for auction in auctions],
            total=total,
            limit=filters.limit,
            offset=filters.offset,
        )

    def _to_record(self, auction: Auction) -> AuctionListingRecord:
        marketplace = auction.marketplace
        domain = auction.domain
        return AuctionListingRecord(
            id=auction.id,
            source_item_id=auction.source_item_id,
            source_url=auction.source_url,
            auction_type=auction.auction_type.value,
            status=auction.status.value,
            starts_at=auction.starts_at,
            ends_at=auction.ends_at,
            current_bid=_money_value(auction.current_bid_amount, auction.currency),
            min_bid=_money_value(auction.min_bid_amount, auction.currency),
            bid_count=auction.bid_count,
            watchers_count=auction.watchers_count,
            first_seen_at=auction.first_seen_at,
            last_seen_at=auction.last_seen_at,
            closed_at=auction.closed_at,
            marketplace=MarketplaceSummary(
                id=marketplace.id,
                code=marketplace.code,
                display_name=marketplace.display_name,
            ),
            domain=DomainSummary(
                id=domain.id,
                fqdn=domain.fqdn,
                sld=domain.sld,
                tld=domain.tld,
                punycode_fqdn=domain.punycode_fqdn,
                unicode_fqdn=domain.unicode_fqdn,
                is_valid=domain.is_valid,
            ),
        )


def _money_value(amount: Optional[Decimal], currency: Optional[str]) -> Optional[MoneyValue]:
    """Return a complete money object only when amount and currency are verified."""

    if amount is None or not currency:
        return None
    normalized_amount = Decimal(amount).quantize(Decimal("0.01"))
    return MoneyValue(amount=str(normalized_amount), currency=currency)
