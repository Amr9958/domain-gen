"""Marketplace ingestion ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain_intel.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class SourceMarketplace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registry of marketplaces and source settings."""

    __tablename__ = "source_marketplaces"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text)
    terms_review_status: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ingest_runs: Mapped[List["IngestRun"]] = relationship(back_populates="marketplace")
    raw_items: Mapped[List["RawAuctionItem"]] = relationship(back_populates="marketplace")
    auctions: Mapped[List["Auction"]] = relationship(back_populates="marketplace")


class IngestRun(UUIDPrimaryKeyMixin, Base):
    """Each marketplace ingestion attempt."""

    __tablename__ = "ingest_runs"
    __table_args__ = (
        Index("ix_ingest_runs_marketplace_started_at", "marketplace_id", "started_at"),
        Index("ix_ingest_runs_status_started_at", "status", "started_at"),
    )

    marketplace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_marketplaces.id"),
        nullable=False,
    )
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_version: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    metrics_json: Mapped[Dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    marketplace: Mapped[SourceMarketplace] = relationship(back_populates="ingest_runs")
    raw_items: Mapped[List["RawAuctionItem"]] = relationship(back_populates="ingest_run")


class RawAuctionItem(UUIDPrimaryKeyMixin, Base):
    """Raw marketplace observation before normalization."""

    __tablename__ = "raw_auction_items"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_id",
            "source_item_id",
            "raw_payload_hash",
            name="uq_raw_auction_items_marketplace_source_hash",
        ),
        CheckConstraint(
            "raw_payload_json is not null or raw_artifact_uri is not null",
            name="raw_auction_items_payload_or_artifact_required",
        ),
    )

    ingest_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_runs.id"),
        nullable=False,
    )
    marketplace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_marketplaces.id"),
        nullable=False,
    )
    source_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    raw_payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload_json: Mapped[Optional[Dict[str, object]]] = mapped_column(JSONB)
    raw_artifact_uri: Mapped[Optional[str]] = mapped_column(Text)
    adapter_version: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)

    ingest_run: Mapped[IngestRun] = relationship(back_populates="raw_items")
    marketplace: Mapped[SourceMarketplace] = relationship(back_populates="raw_items")
    snapshots: Mapped[List["AuctionSnapshot"]] = relationship(back_populates="raw_auction_item")
