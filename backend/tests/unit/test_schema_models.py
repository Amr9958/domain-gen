"""Schema model smoke tests."""

from __future__ import annotations

import pytest


pytest.importorskip("sqlalchemy")

from domain_intel.core.enums import (
    AuctionStatus,
    EnrichmentStatus,
    MarketplaceCode,
    StarterDomainLabel,
    ValuationRefusalCode,
    ValueTier,
    WebsitePageCategory,
)
from domain_intel.db.base import Base
import domain_intel.db.models  # noqa: F401


def test_metadata_contains_shared_schema_tables() -> None:
    expected_tables = {
        "organizations",
        "users",
        "organization_members",
        "source_marketplaces",
        "ingest_runs",
        "raw_auction_items",
        "domains",
        "auctions",
        "auction_snapshots",
        "verified_facts",
        "enrichment_runs",
        "website_checks",
        "derived_signals",
        "classification_results",
        "valuation_runs",
        "valuation_reason_codes",
        "ai_explanations",
        "appraisal_reports",
        "watchlists",
        "watchlist_items",
        "alert_rules",
        "alert_events",
        "alert_deliveries",
        "audit_log",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_core_guardrail_enums_include_refusal_and_marketplace_states() -> None:
    assert MarketplaceCode.DYNADOT.value == "dynadot"
    assert AuctionStatus.UNKNOWN.value == "unknown"
    assert ValuationRefusalCode.LEGAL_OR_TRADEMARK_RISK.value == "legal_or_trademark_risk"
    assert ValueTier.REFUSAL.value == "refusal"
    assert EnrichmentStatus.PARTIAL.value == "partial"
    assert WebsitePageCategory.SALES_LANDING_PAGE.value == "sales_landing_page"
    assert StarterDomainLabel.GEO_SERVICE.value == "geo_service"
