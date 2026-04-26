"""initial domain intelligence schema

Revision ID: 20260423180000
Revises:
Create Date: 2026-04-23 18:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260423180000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


auction_status = postgresql.ENUM(
    "scheduled",
    "open",
    "closing",
    "closed",
    "sold",
    "unsold",
    "cancelled",
    "unknown",
    name="auction_status",
    create_type=False,
)
auction_type = postgresql.ENUM(
    "expired",
    "closeout",
    "backorder",
    "private_seller",
    "registry",
    "unknown",
    name="auction_type",
    create_type=False,
)
domain_type = postgresql.ENUM(
    "exact_match",
    "brandable",
    "keyword_phrase",
    "acronym",
    "numeric",
    "geo",
    "personal_name",
    "premium_generic",
    "typo_risk",
    "adult_or_sensitive",
    "unknown",
    name="domain_type",
    create_type=False,
)
valuation_status = postgresql.ENUM(
    "valued",
    "refused",
    "needs_review",
    name="valuation_status",
    create_type=False,
)
valuation_refusal_code = postgresql.ENUM(
    "insufficient_evidence",
    "missing_classification",
    "unsupported_domain_type",
    "legal_or_trademark_risk",
    "invalid_domain",
    "stale_inputs",
    "conflicting_facts",
    "provider_failure",
    name="valuation_refusal_code",
    create_type=False,
)
confidence_level = postgresql.ENUM(
    "low",
    "medium",
    "high",
    name="confidence_level",
    create_type=False,
)
value_tier = postgresql.ENUM(
    "refusal",
    "low",
    "meaningful",
    "high",
    "premium",
    name="value_tier",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    for enum_type in (
        auction_status,
        auction_type,
        domain_type,
        valuation_status,
        valuation_refusal_code,
        confidence_level,
        value_tier,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("plan_code", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "source_marketplaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text()),
        sa.Column("terms_review_status", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_source_marketplaces_code"),
    )
    op.create_table(
        "domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("fqdn", sa.Text(), nullable=False),
        sa.Column("sld", sa.Text(), nullable=False),
        sa.Column("tld", sa.Text(), nullable=False),
        sa.Column("punycode_fqdn", sa.Text(), nullable=False),
        sa.Column("unicode_fqdn", sa.Text()),
        sa.Column("is_valid", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fqdn", name="uq_domains_fqdn"),
    )
    op.create_index("ix_domains_tld_sld", "domains", ["tld", "sld"])
    op.create_index("ix_domains_punycode_fqdn", "domains", ["punycode_fqdn"])

    op.create_table(
        "organization_members",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role in ('owner', 'analyst', 'viewer')", name="organization_members_role_allowed"),
    )
    op.create_table(
        "ingest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("marketplace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_marketplaces.id"), nullable=False),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("metrics_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.execute("CREATE INDEX ix_ingest_runs_marketplace_started_at ON ingest_runs (marketplace_id, started_at DESC)")
    op.execute("CREATE INDEX ix_ingest_runs_status_started_at ON ingest_runs (status, started_at DESC)")

    op.create_table(
        "raw_auction_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ingest_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest_runs.id"), nullable=False),
        sa.Column("marketplace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_marketplaces.id"), nullable=False),
        sa.Column("source_item_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload_hash", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", postgresql.JSONB()),
        sa.Column("raw_artifact_uri", sa.Text()),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "raw_payload_json is not null or raw_artifact_uri is not null",
            name="raw_auction_items_payload_or_artifact_required",
        ),
        sa.UniqueConstraint(
            "marketplace_id",
            "source_item_id",
            "raw_payload_hash",
            name="uq_raw_auction_items_marketplace_source_hash",
        ),
    )
    op.create_table(
        "auctions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("marketplace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_marketplaces.id"), nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("source_item_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("auction_type", auction_type, nullable=False),
        sa.Column("status", auction_status, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("currency", sa.CHAR(length=3)),
        sa.Column("current_bid_amount", sa.Numeric(14, 2)),
        sa.Column("min_bid_amount", sa.Numeric(14, 2)),
        sa.Column("bid_count", sa.Integer()),
        sa.Column("watchers_count", sa.Integer()),
        sa.Column("normalized_payload_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "starts_at is null or ends_at is null or ends_at > starts_at",
            name="auctions_ends_after_starts",
        ),
        sa.UniqueConstraint("marketplace_id", "source_item_id", name="uq_auctions_marketplace_source_item"),
    )
    op.execute("CREATE INDEX ix_auctions_domain_last_seen_at ON auctions (domain_id, last_seen_at DESC)")
    op.create_index("ix_auctions_status_ends_at", "auctions", ["status", "ends_at"])
    op.execute("CREATE INDEX ix_auctions_marketplace_last_seen_at ON auctions (marketplace_id, last_seen_at DESC)")

    op.create_table(
        "auction_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("auction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auctions.id"), nullable=False),
        sa.Column("raw_auction_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_auction_items.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", auction_status, nullable=False),
        sa.Column("current_bid_amount", sa.Numeric(14, 2)),
        sa.Column("currency", sa.CHAR(length=3)),
        sa.Column("bid_count", sa.Integer()),
        sa.Column("watchers_count", sa.Integer()),
        sa.Column("snapshot_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.UniqueConstraint("auction_id", "captured_at", name="uq_auction_snapshots_auction_captured_at"),
    )
    op.create_table(
        "verified_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id")),
        sa.Column("auction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auctions.id")),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_value_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("evidence_ref", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("provider_version", sa.Text()),
        sa.Column("parser_version", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute("CREATE INDEX ix_verified_facts_domain_fact_type_observed_at ON verified_facts (domain_id, fact_type, observed_at DESC)")
    op.execute("CREATE INDEX ix_verified_facts_auction_fact_type_observed_at ON verified_facts (auction_id, fact_type, observed_at DESC)")

    op.create_table(
        "enrichment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("raw_artifact_uri", sa.Text()),
        sa.Column("created_fact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
    )
    op.execute("CREATE INDEX ix_enrichment_runs_domain_started_at ON enrichment_runs (domain_id, started_at DESC)")
    op.execute("CREATE INDEX ix_enrichment_runs_provider_status_started_at ON enrichment_runs (provider, status, started_at DESC)")

    op.create_table(
        "website_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text()),
        sa.Column("http_status", sa.Integer()),
        sa.Column("redirect_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("tls_valid", sa.Boolean()),
        sa.Column("title", sa.Text()),
        sa.Column("content_hash", sa.Text()),
        sa.Column("technology_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_fact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
    )
    op.create_table(
        "derived_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("auction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auctions.id")),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("signal_key", sa.Text(), nullable=False),
        sa.Column("signal_value_json", postgresql.JSONB(), nullable=False),
        sa.Column("input_fact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("input_signal_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("algorithm_version", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("CREATE INDEX ix_derived_signals_domain_signal_type_generated_at ON derived_signals (domain_id, signal_type, generated_at DESC)")
    op.execute("CREATE INDEX ix_derived_signals_auction_signal_type_generated_at ON derived_signals (auction_id, signal_type, generated_at DESC)")

    op.create_table(
        "classification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("domain_type", domain_type, nullable=False),
        sa.Column("business_category", sa.Text()),
        sa.Column("language_code", sa.Text()),
        sa.Column("tokens_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("risk_flags_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("algorithm_version", sa.Text(), nullable=False),
        sa.Column("input_fact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("input_signal_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("refusal_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute("CREATE INDEX ix_classification_results_domain_created_at ON classification_results (domain_id, created_at DESC)")
    op.execute("CREATE INDEX ix_classification_results_domain_type_confidence_score ON classification_results (domain_type, confidence_score DESC)")

    op.create_table(
        "valuation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("auction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auctions.id")),
        sa.Column("classification_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("classification_results.id")),
        sa.Column("status", valuation_status, nullable=False),
        sa.Column("refusal_code", valuation_refusal_code),
        sa.Column("refusal_reason", sa.Text()),
        sa.Column("estimated_value_min", sa.Numeric(14, 2)),
        sa.Column("estimated_value_max", sa.Numeric(14, 2)),
        sa.Column("estimated_value_point", sa.Numeric(14, 2)),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("value_tier", value_tier, nullable=False),
        sa.Column("confidence_level", confidence_level, nullable=False),
        sa.Column("algorithm_version", sa.Text(), nullable=False),
        sa.Column("input_fact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("input_signal_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status != 'valued' or classification_result_id is not null", name="valuation_runs_classification_required_when_valued"),
        sa.CheckConstraint("status != 'refused' or refusal_code is not null", name="valuation_runs_refusal_code_required_when_refused"),
        sa.CheckConstraint(
            "status != 'valued' or (estimated_value_min is not null and estimated_value_max is not null)",
            name="valuation_runs_range_required_when_valued",
        ),
        sa.CheckConstraint(
            "estimated_value_min is null or estimated_value_max is null or estimated_value_min <= estimated_value_max",
            name="valuation_runs_min_lte_max",
        ),
        sa.CheckConstraint("status != 'refused' or value_tier = 'refusal'", name="valuation_runs_refused_tier_is_refusal"),
    )
    op.execute("CREATE INDEX ix_valuation_runs_domain_created_at ON valuation_runs (domain_id, created_at DESC)")
    op.execute("CREATE INDEX ix_valuation_runs_auction_created_at ON valuation_runs (auction_id, created_at DESC)")
    op.execute("CREATE INDEX ix_valuation_runs_status_value_tier_created_at ON valuation_runs (status, value_tier, created_at DESC)")

    op.create_table(
        "valuation_reason_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("valuation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("valuation_runs.id"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("impact_amount", sa.Numeric(14, 2)),
        sa.Column("impact_weight", sa.Numeric(6, 4)),
        sa.Column("evidence_refs_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.CheckConstraint("direction in ('positive', 'negative', 'neutral')", name="valuation_reason_codes_direction_allowed"),
    )
    op.create_table(
        "ai_explanations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("explanation_type", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("input_refs_json", postgresql.JSONB(), nullable=False),
        sa.Column("structured_output_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "validation_status in ('pending', 'validated', 'rejected')",
            name="ai_explanations_validation_status_allowed",
        ),
    )
    op.create_table(
        "appraisal_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("valuation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("valuation_runs.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("report_template_version", sa.Text(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column("public_token", sa.Text()),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("public_token", name="uq_appraisal_reports_public_token"),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("visibility in ('private', 'organization')", name="watchlists_visibility_allowed"),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("watchlist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id")),
        sa.Column("auction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auctions.id")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("domain_id is not null or auction_id is not null", name="watchlist_items_domain_or_auction_required"),
        sa.UniqueConstraint("watchlist_id", "domain_id", "auction_id", name="uq_watchlist_items_watchlist_domain_auction"),
    )
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("watchlist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("threshold_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("channel_config_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id"), nullable=False),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domains.id")),
        sa.Column("auction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auctions.id")),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_key", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("alert_rule_id", "event_key", name="uq_alert_events_rule_event_key"),
    )
    op.create_table(
        "alert_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("alert_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_events.id"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_summary", sa.Text()),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id")),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payload_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    for table_name in (
        "audit_log",
        "alert_deliveries",
        "alert_events",
        "alert_rules",
        "watchlist_items",
        "watchlists",
        "appraisal_reports",
        "ai_explanations",
        "valuation_reason_codes",
        "valuation_runs",
        "classification_results",
        "derived_signals",
        "website_checks",
        "enrichment_runs",
        "verified_facts",
        "auction_snapshots",
        "auctions",
        "raw_auction_items",
        "ingest_runs",
        "organization_members",
        "domains",
        "source_marketplaces",
        "users",
        "organizations",
    ):
        op.drop_table(table_name)

    bind = op.get_bind()
    for enum_type in (
        value_tier,
        confidence_level,
        valuation_refusal_code,
        valuation_status,
        domain_type,
        auction_type,
        auction_status,
    ):
        enum_type.drop(bind, checkfirst=True)
