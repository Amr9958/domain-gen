"""Shared typed models for signal ingestion and domain intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SourceType(StrEnum):
    """Top-level signal source categories."""

    NEWS = "news"
    DEVELOPER = "developer"
    REPOSITORY = "repository"
    RELEASE = "release"
    PRODUCT = "product"


class ItemClassification(StrEnum):
    """Opportunity-quality buckets used throughout the pipeline."""

    INVESTABLE = "investable"
    WATCHLIST = "watchlist"
    LOW_VALUE = "low_value"
    IGNORE = "ignore"


class DomainRecommendation(StrEnum):
    """Final investor-facing action labels."""

    BUY = "buy"
    WATCH = "watch"
    SKIP = "skip"


@dataclass(frozen=True)
class ContentItem:
    """Normalized source item shared by collectors and processors."""

    source_name: str
    source_type: SourceType
    title: str
    url: str
    content_hash: str
    fetched_at: datetime
    published_at: datetime | None = None
    body: str = ""
    summary: str = ""
    author: str = ""
    language: str = "en"
    tags: tuple[str, ...] = ()
    raw_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Theme:
    """Clustered higher-level trend theme."""

    canonical_name: str
    description: str
    classification: ItemClassification
    source_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    momentum_score: float = 0.0
    related_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class KeywordInsight:
    """Commercial keyword or naming component extracted from a theme."""

    keyword: str
    keyword_type: str
    theme_name: str
    classification: ItemClassification
    niche: str = ""
    buyer_type: str = ""
    commercial_score: float = 0.0
    novelty_score: float = 0.0
    brandability_score: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class DomainOpportunity:
    """Trend-derived domain opportunity ready for scoring and review."""

    domain_name: str
    extension: str
    source_theme: str
    recommendation: DomainRecommendation
    keyword: str = ""
    niche: str = ""
    buyer_type: str = ""
    style: str = ""
    score: float = 0.0
    rationale: str = ""
    risk_notes: tuple[str, ...] = ()
    rejected_reason: str = ""


@dataclass(frozen=True)
class ProcessingRun:
    """Execution metadata for collection and processing jobs."""

    job_name: str
    started_at: datetime
    status: str
    run_id: str = ""
    ended_at: datetime | None = None
    notes: str = ""
