"""Shared enums from db_schema.md and stable status types."""

from __future__ import annotations

from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 compatibility
    class StrEnum(str, Enum):
        """Small compatibility shim for string-valued enums."""


class MarketplaceCode(StrEnum):
    """Approved marketplace codes from the shared schema."""

    DYNADOT = "dynadot"
    DROPCATCH = "dropcatch"
    MANUAL_IMPORT = "manual_import"


class AuctionStatus(StrEnum):
    """Canonical auction lifecycle statuses."""

    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    SOLD = "sold"
    UNSOLD = "unsold"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class AuctionType(StrEnum):
    """Canonical auction source/type buckets."""

    EXPIRED = "expired"
    CLOSEOUT = "closeout"
    BACKORDER = "backorder"
    PRIVATE_SELLER = "private_seller"
    REGISTRY = "registry"
    UNKNOWN = "unknown"


class DomainType(StrEnum):
    """Domain classification output types."""

    EXACT_MATCH = "exact_match"
    BRANDABLE = "brandable"
    KEYWORD_PHRASE = "keyword_phrase"
    ACRONYM = "acronym"
    NUMERIC = "numeric"
    GEO = "geo"
    PERSONAL_NAME = "personal_name"
    PREMIUM_GENERIC = "premium_generic"
    TYPO_RISK = "typo_risk"
    ADULT_OR_SENSITIVE = "adult_or_sensitive"
    UNKNOWN = "unknown"


class ValuationStatus(StrEnum):
    """Valuation run terminal or review states."""

    VALUED = "valued"
    REFUSED = "refused"
    NEEDS_REVIEW = "needs_review"


class ValuationRefusalCode(StrEnum):
    """Stable refusal codes for valuation prerequisites and risk gates."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MISSING_CLASSIFICATION = "missing_classification"
    UNSUPPORTED_DOMAIN_TYPE = "unsupported_domain_type"
    LEGAL_OR_TRADEMARK_RISK = "legal_or_trademark_risk"
    INVALID_DOMAIN = "invalid_domain"
    STALE_INPUTS = "stale_inputs"
    CONFLICTING_FACTS = "conflicting_facts"
    PROVIDER_FAILURE = "provider_failure"


class ConfidenceLevel(StrEnum):
    """Human-readable confidence labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ValueTier(StrEnum):
    """Valuation tier labels, including refusal as a first-class state."""

    REFUSAL = "refusal"
    LOW = "low"
    MEANINGFUL = "meaningful"
    HIGH = "high"
    PREMIUM = "premium"


class OrganizationRole(StrEnum):
    """Allowed organization membership roles from db_schema.md."""

    OWNER = "owner"
    ANALYST = "analyst"
    VIEWER = "viewer"


class WatchlistVisibility(StrEnum):
    """Allowed watchlist visibility values from db_schema.md."""

    PRIVATE = "private"
    ORGANIZATION = "organization"


class AppraisalReportStatus(StrEnum):
    """Stable lifecycle states for stored appraisal reports."""

    GENERATED = "generated"
    REFUSED = "refused"
    NEEDS_REVIEW = "needs_review"


class AlertRuleType(StrEnum):
    """Supported alert rule types for the investor workflow layer."""

    AUCTION_ENDING_SOON = "auction_ending_soon"
    PRICE_BELOW_THRESHOLD = "price_below_threshold"
    SCORE_ABOVE_THRESHOLD = "score_above_threshold"
    STRONG_UPGRADE_TARGET_FOUND = "strong_upgrade_target_found"
    ENRICHMENT_COMPLETED = "enrichment_completed"


class AlertSeverity(StrEnum):
    """Alert severity labels returned by rule evaluation."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class UndervaluationStatus(StrEnum):
    """Deterministic opportunity screening outcomes."""

    CANDIDATE = "candidate"
    REJECTED = "rejected"
    INSUFFICIENT_DATA = "insufficient_data"


class ReasonDirection(StrEnum):
    """Allowed valuation reason directions from db_schema.md."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class AIExplanationValidationStatus(StrEnum):
    """Allowed AI explanation validation states from db_schema.md."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


class EnrichmentStatus(StrEnum):
    """Stable enrichment lifecycle states used by enrichment runs and providers."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class EnrichmentCheckType(StrEnum):
    """Supported enrichment checks in the phase-5 pipeline."""

    RDAP = "rdap"
    DNS = "dns"
    WEBSITE = "website"


class WebsitePageCategory(StrEnum):
    """Deterministic website inspection categories."""

    ACTIVE_WEBSITE = "active_website"
    PARKED_PAGE = "parked_page"
    SALES_LANDING_PAGE = "sales_landing_page"
    BLANK_INACTIVE = "blank_inactive"
    REDIRECT = "redirect"


class StarterDomainLabel(StrEnum):
    """Rule-based starter labels for explainable domain classification hints."""

    BRANDABLE = "brandable"
    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    GEO_SERVICE = "geo_service"
    AI_TECH = "ai_tech"
    LOCAL_LEAD_GEN = "local_lead_gen"
    SHORT_DOMAIN = "short_domain"
    DICTIONARY_PREMIUM = "dictionary_premium"
    MADE_UP_BRAND = "made_up_brand"
