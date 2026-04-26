"""Domain and auction ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain_intel.core.enums import AuctionStatus, AuctionType
from domain_intel.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from domain_intel.db.types import enum_type


class Domain(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical domain identity."""

    __tablename__ = "domains"
    __table_args__ = (
        Index("ix_domains_tld_sld", "tld", "sld"),
        Index("ix_domains_punycode_fqdn", "punycode_fqdn"),
    )

    fqdn: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sld: Mapped[str] = mapped_column(Text, nullable=False)
    tld: Mapped[str] = mapped_column(Text, nullable=False)
    punycode_fqdn: Mapped[str] = mapped_column(Text, nullable=False)
    unicode_fqdn: Mapped[Optional[str]] = mapped_column(Text)
    is_valid: Mapped[bool] = mapped_column(nullable=False, default=True)

    auctions: Mapped[List["Auction"]] = relationship(back_populates="domain")


class Auction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical current auction state."""

    __tablename__ = "auctions"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_id",
            "source_item_id",
            name="uq_auctions_marketplace_source_item",
        ),
        CheckConstraint(
            "starts_at is null or ends_at is null or ends_at > starts_at",
            name="auctions_ends_after_starts",
        ),
        Index("ix_auctions_domain_last_seen_at", "domain_id", "last_seen_at"),
        Index("ix_auctions_status_ends_at", "status", "ends_at"),
        Index("ix_auctions_marketplace_last_seen_at", "marketplace_id", "last_seen_at"),
    )

    marketplace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_marketplaces.id"),
        nullable=False,
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    source_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    auction_type: Mapped[AuctionType] = mapped_column(
        enum_type(AuctionType, "auction_type"),
        nullable=False,
    )
    status: Mapped[AuctionStatus] = mapped_column(
        enum_type(AuctionStatus, "auction_status"),
        nullable=False,
    )
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    currency: Mapped[Optional[str]] = mapped_column(CHAR(3))
    current_bid_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    min_bid_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    bid_count: Mapped[Optional[int]] = mapped_column(Integer)
    watchers_count: Mapped[Optional[int]] = mapped_column(Integer)
    normalized_payload_json: Mapped[Dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    marketplace: Mapped["SourceMarketplace"] = relationship(back_populates="auctions")
    domain: Mapped[Domain] = relationship(back_populates="auctions")
    snapshots: Mapped[List["AuctionSnapshot"]] = relationship(back_populates="auction")


class AuctionSnapshot(UUIDPrimaryKeyMixin, Base):
    """Historical auction observation."""

    __tablename__ = "auction_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "auction_id",
            "captured_at",
            name="uq_auction_snapshots_auction_captured_at",
        ),
    )

    auction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auctions.id"),
        nullable=False,
    )
    raw_auction_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_auction_items.id"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AuctionStatus] = mapped_column(
        enum_type(AuctionStatus, "auction_status"),
        nullable=False,
    )
    current_bid_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency: Mapped[Optional[str]] = mapped_column(CHAR(3))
    bid_count: Mapped[Optional[int]] = mapped_column(Integer)
    watchers_count: Mapped[Optional[int]] = mapped_column(Integer)
    snapshot_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    auction: Mapped[Auction] = relationship(back_populates="snapshots")
    raw_auction_item: Mapped["RawAuctionItem"] = relationship(back_populates="snapshots")
