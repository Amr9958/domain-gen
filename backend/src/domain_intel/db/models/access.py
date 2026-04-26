"""SaaS access and organization ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from sqlalchemy.dialects.postgresql import CITEXT
except ImportError:  # pragma: no cover - older SQLAlchemy fallback
    CITEXT = Text

from domain_intel.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Customer account container."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    plan_code: Mapped[str] = mapped_column(Text, nullable=False)

    members: Mapped[List["OrganizationMember"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Application user identity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(Text)

    memberships: Mapped[List["OrganizationMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class OrganizationMember(Base):
    """User membership within an organization."""

    __tablename__ = "organization_members"
    __table_args__ = (
        CheckConstraint(
            "role in ('owner', 'analyst', 'viewer')",
            name="organization_members_role_allowed",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")
