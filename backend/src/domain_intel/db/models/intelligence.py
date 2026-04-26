"""Evidence, enrichment, signal, classification, valuation, and AI models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain_intel.core.enums import (
    ConfidenceLevel,
    DomainType,
    ValuationRefusalCode,
    ValuationStatus,
    ValueTier,
)
from domain_intel.db.base import Base, UUIDPrimaryKeyMixin, utc_now
from domain_intel.db.types import enum_type


class VerifiedFact(UUIDPrimaryKeyMixin, Base):
    """Evidence-backed observation, never an AI summary or derived score."""

    __tablename__ = "verified_facts"
    __table_args__ = (
        Index("ix_verified_facts_domain_fact_type_observed_at", "domain_id", "fact_type", "observed_at"),
        Index("ix_verified_facts_auction_fact_type_observed_at", "auction_id", "fact_type", "observed_at"),
    )

    domain_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
    )
    auction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auctions.id"),
    )
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_system: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    evidence_ref: Mapped[Optional[str]] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    provider_version: Mapped[Optional[str]] = mapped_column(Text)
    parser_version: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class EnrichmentRun(UUIDPrimaryKeyMixin, Base):
    """Enrichment attempt metadata."""

    __tablename__ = "enrichment_runs"
    __table_args__ = (
        Index("ix_enrichment_runs_domain_started_at", "domain_id", "started_at"),
        Index("ix_enrichment_runs_provider_status_started_at", "provider", "status", "started_at"),
    )

    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    raw_artifact_uri: Mapped[Optional[str]] = mapped_column(Text)
    created_fact_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )


class WebsiteCheck(UUIDPrimaryKeyMixin, Base):
    """Parsed website check results and links to facts."""

    __tablename__ = "website_checks"

    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[Optional[str]] = mapped_column(Text)
    http_status: Mapped[Optional[int]]
    redirect_count: Mapped[int] = mapped_column(nullable=False, default=0)
    tls_valid: Mapped[Optional[bool]]
    title: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[Optional[str]] = mapped_column(Text)
    technology_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_fact_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )


class DerivedSignal(UUIDPrimaryKeyMixin, Base):
    """Computed signal from facts, domain text, and auction history."""

    __tablename__ = "derived_signals"
    __table_args__ = (
        Index("ix_derived_signals_domain_signal_type_generated_at", "domain_id", "signal_type", "generated_at"),
        Index("ix_derived_signals_auction_signal_type_generated_at", "auction_id", "signal_type", "generated_at"),
    )

    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    auction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auctions.id"),
    )
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    signal_key: Mapped[str] = mapped_column(Text, nullable=False)
    signal_value_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False)
    input_fact_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    input_signal_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    algorithm_version: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClassificationResult(UUIDPrimaryKeyMixin, Base):
    """Domain classification result required before valuation."""

    __tablename__ = "classification_results"
    __table_args__ = (
        Index("ix_classification_results_domain_created_at", "domain_id", "created_at"),
        Index("ix_classification_results_domain_type_confidence_score", "domain_type", "confidence_score"),
    )

    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    domain_type: Mapped[DomainType] = mapped_column(enum_type(DomainType, "domain_type"), nullable=False)
    business_category: Mapped[Optional[str]] = mapped_column(Text)
    language_code: Mapped[Optional[str]] = mapped_column(Text)
    tokens_json: Mapped[List[object]] = mapped_column(JSONB, nullable=False, default=list)
    risk_flags_json: Mapped[List[object]] = mapped_column(JSONB, nullable=False, default=list)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_fact_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    input_signal_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    refusal_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    valuation_runs: Mapped[List["ValuationRun"]] = relationship(back_populates="classification_result")


class ValuationRun(UUIDPrimaryKeyMixin, Base):
    """Explainable valuation output or refusal state."""

    __tablename__ = "valuation_runs"
    __table_args__ = (
        CheckConstraint(
            "status != 'valued' or classification_result_id is not null",
            name="valuation_runs_classification_required_when_valued",
        ),
        CheckConstraint(
            "status != 'refused' or refusal_code is not null",
            name="valuation_runs_refusal_code_required_when_refused",
        ),
        CheckConstraint(
            "status != 'valued' or (estimated_value_min is not null and estimated_value_max is not null)",
            name="valuation_runs_range_required_when_valued",
        ),
        CheckConstraint(
            "estimated_value_min is null or estimated_value_max is null or estimated_value_min <= estimated_value_max",
            name="valuation_runs_min_lte_max",
        ),
        CheckConstraint(
            "status != 'refused' or value_tier = 'refusal'",
            name="valuation_runs_refused_tier_is_refusal",
        ),
        Index("ix_valuation_runs_domain_created_at", "domain_id", "created_at"),
        Index("ix_valuation_runs_auction_created_at", "auction_id", "created_at"),
        Index("ix_valuation_runs_status_value_tier_created_at", "status", "value_tier", "created_at"),
    )

    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id"),
        nullable=False,
    )
    auction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auctions.id"),
    )
    classification_result_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classification_results.id"),
    )
    status: Mapped[ValuationStatus] = mapped_column(
        enum_type(ValuationStatus, "valuation_status"),
        nullable=False,
    )
    refusal_code: Mapped[Optional[ValuationRefusalCode]] = mapped_column(
        enum_type(ValuationRefusalCode, "valuation_refusal_code"),
    )
    refusal_reason: Mapped[Optional[str]] = mapped_column(Text)
    estimated_value_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    estimated_value_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    estimated_value_point: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="USD")
    value_tier: Mapped[ValueTier] = mapped_column(enum_type(ValueTier, "value_tier"), nullable=False)
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        enum_type(ConfidenceLevel, "confidence_level"),
        nullable=False,
    )
    algorithm_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_fact_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    input_signal_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    classification_result: Mapped[Optional[ClassificationResult]] = relationship(back_populates="valuation_runs")
    reason_codes: Mapped[List["ValuationReasonCode"]] = relationship(
        back_populates="valuation_run",
        cascade="all, delete-orphan",
    )


class ValuationReasonCode(UUIDPrimaryKeyMixin, Base):
    """Structured valuation reasoning tied to stored evidence refs."""

    __tablename__ = "valuation_reason_codes"
    __table_args__ = (
        CheckConstraint(
            "direction in ('positive', 'negative', 'neutral')",
            name="valuation_reason_codes_direction_allowed",
        ),
    )

    valuation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("valuation_runs.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    impact_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    impact_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    evidence_refs_json: Mapped[List[object]] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    valuation_run: Mapped[ValuationRun] = relationship(back_populates="reason_codes")


class AIExplanation(UUIDPrimaryKeyMixin, Base):
    """AI-generated narrative that can feed reports only after validation."""

    __tablename__ = "ai_explanations"
    __table_args__ = (
        CheckConstraint(
            "validation_status in ('pending', 'validated', 'rejected')",
            name="ai_explanations_validation_status_allowed",
        ),
    )

    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    explanation_type: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_refs_json: Mapped[List[object]] = mapped_column(JSONB, nullable=False)
    structured_output_json: Mapped[Dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
