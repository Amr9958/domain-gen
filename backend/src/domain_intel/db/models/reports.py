"""Report, watchlist, and alert ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain_intel.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class AppraisalReport(UUIDPrimaryKeyMixin, Base):
    """Reproducible appraisal report record."""

    __tablename__ = "appraisal_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    valuation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("valuation_runs.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    report_template_version: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False)
    public_token: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User or organization watchlist."""

    __tablename__ = "watchlists"
    __table_args__ = (
        CheckConstraint(
            "visibility in ('private', 'organization')",
            name="watchlists_visibility_allowed",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class WatchlistItem(UUIDPrimaryKeyMixin, Base):
    """Watched domain and/or auction."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        CheckConstraint(
            "domain_id is not null or auction_id is not null",
            name="watchlist_items_domain_or_auction_required",
        ),
        UniqueConstraint(
            "watchlist_id",
            "domain_id",
            "auction_id",
            name="uq_watchlist_items_watchlist_domain_auction",
        ),
    )

    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("watchlists.id"),
        nullable=False,
    )
    domain_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
    )
    auction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auctions.id"),
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )


class AlertRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable alert rule."""

    __tablename__ = "alert_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("watchlists.id"),
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    threshold_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    channel_config_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class AlertEvent(UUIDPrimaryKeyMixin, Base):
    """Deduplicated alert event."""

    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("alert_rule_id", "event_key", name="uq_alert_events_rule_event_key"),
    )

    alert_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id"),
        nullable=False,
    )
    domain_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
    )
    auction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auctions.id"),
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_key: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AlertDelivery(UUIDPrimaryKeyMixin, Base):
    """Delivery attempts for alert events."""

    __tablename__ = "alert_deliveries"

    alert_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_events.id"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
