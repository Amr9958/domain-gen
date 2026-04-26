"""Audit ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain_intel.db.base import Base, UUIDPrimaryKeyMixin, utc_now


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only record of important user and system actions."""

    __tablename__ = "audit_log"

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    payload_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
