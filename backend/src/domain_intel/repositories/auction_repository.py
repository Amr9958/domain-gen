"""Auction listing repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import joinedload

from domain_intel.core.enums import AuctionStatus
from domain_intel.db.models import Auction, Domain, SourceMarketplace
from domain_intel.repositories.base import BaseRepository


@dataclass(frozen=True)
class AuctionQueryFilters:
    """Database query filters for normalized auction listings."""

    source: Optional[str] = None
    tld: Optional[str] = None
    closes_after: Optional[datetime] = None
    closes_before: Optional[datetime] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    status: Optional[AuctionStatus] = None
    limit: int = 50
    offset: int = 0

    @property
    def normalized_tld(self) -> Optional[str]:
        """Normalize user-facing TLD filters without changing stored names."""

        if self.tld is None:
            return None
        normalized = self.tld.strip().lower()
        if normalized.startswith("."):
            normalized = normalized[1:]
        return normalized or None


class AuctionRepository(BaseRepository):
    """Read repository for canonical auction listings."""

    def list_listings(self, filters: AuctionQueryFilters) -> Tuple[List[Auction], int]:
        """Return matching auctions and total count for the same filter set."""

        criteria = self._criteria(filters)

        count_statement = (
            select(func.count(Auction.id))
            .join(Auction.domain)
            .join(Auction.marketplace)
            .where(*criteria)
        )
        total = int(self.session.scalar(count_statement) or 0)

        statement = (
            select(Auction)
            .join(Auction.domain)
            .join(Auction.marketplace)
            .options(joinedload(Auction.domain), joinedload(Auction.marketplace))
            .where(*criteria)
            .order_by(Auction.ends_at.asc().nulls_last(), Auction.last_seen_at.desc())
            .limit(filters.limit)
            .offset(filters.offset)
        )
        rows = list(self.session.scalars(statement).all())
        return rows, total

    def _criteria(self, filters: AuctionQueryFilters) -> list:
        criteria = []
        if filters.source:
            criteria.append(SourceMarketplace.code == filters.source)
        if filters.normalized_tld:
            criteria.append(Domain.tld == filters.normalized_tld)
        if filters.closes_after is not None:
            criteria.append(Auction.ends_at >= filters.closes_after)
        if filters.closes_before is not None:
            criteria.append(Auction.ends_at <= filters.closes_before)
        if filters.min_price is not None:
            criteria.append(Auction.current_bid_amount >= filters.min_price)
        if filters.max_price is not None:
            criteria.append(Auction.current_bid_amount <= filters.max_price)
        if filters.status is not None:
            criteria.append(Auction.status == filters.status)
        return criteria

    def statement_for_filters(self, filters: AuctionQueryFilters) -> Select:
        """Expose the generated query shape for focused repository tests."""

        return (
            select(Auction)
            .join(Auction.domain)
            .join(Auction.marketplace)
            .where(*self._criteria(filters))
        )
