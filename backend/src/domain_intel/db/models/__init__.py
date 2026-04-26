"""Import all ORM models so Alembic can see complete metadata."""

from domain_intel.db.models.access import Organization, OrganizationMember, User
from domain_intel.db.models.audit import AuditLog
from domain_intel.db.models.domain import Auction, AuctionSnapshot, Domain
from domain_intel.db.models.intelligence import (
    AIExplanation,
    ClassificationResult,
    DerivedSignal,
    EnrichmentRun,
    ValuationReasonCode,
    ValuationRun,
    VerifiedFact,
    WebsiteCheck,
)
from domain_intel.db.models.marketplace import IngestRun, RawAuctionItem, SourceMarketplace
from domain_intel.db.models.reports import (
    AlertDelivery,
    AlertEvent,
    AlertRule,
    AppraisalReport,
    Watchlist,
    WatchlistItem,
)

__all__ = [
    "AIExplanation",
    "AlertDelivery",
    "AlertEvent",
    "AlertRule",
    "AppraisalReport",
    "AuditLog",
    "Auction",
    "AuctionSnapshot",
    "ClassificationResult",
    "DerivedSignal",
    "Domain",
    "EnrichmentRun",
    "IngestRun",
    "Organization",
    "OrganizationMember",
    "RawAuctionItem",
    "SourceMarketplace",
    "User",
    "ValuationReasonCode",
    "ValuationRun",
    "VerifiedFact",
    "Watchlist",
    "WatchlistItem",
    "WebsiteCheck",
]
