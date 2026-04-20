"""Shared helpers for unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

from models import (
    ContentItem,
    DomainOpportunity,
    DomainRecommendation,
    ItemClassification,
    KeywordInsight,
    ProcessedSignal,
    SourceType,
    Theme,
)


TEST_NOW = datetime(2026, 4, 19, tzinfo=timezone.utc)


def make_content_item(
    *,
    title: str,
    summary: str = "",
    body: str = "",
    tags: tuple[str, ...] = (),
    content_hash: str | None = None,
    source_name: str = "github",
    source_type: SourceType = SourceType.REPOSITORY,
) -> ContentItem:
    """Build a minimal normalized content item for tests."""
    stable_hash = content_hash or title.lower().replace(" ", "-")
    return ContentItem(
        source_name=source_name,
        source_type=source_type,
        title=title,
        url=f"https://example.com/{stable_hash}",
        body=body,
        summary=summary,
        author="tester",
        language="en",
        content_hash=stable_hash,
        published_at=TEST_NOW,
        fetched_at=TEST_NOW,
        tags=tags,
        raw_payload={},
    )


def make_theme(
    canonical_name: str,
    *,
    classification: ItemClassification = ItemClassification.INVESTABLE,
    momentum_score: float = 6.0,
    source_count: int = 3,
    related_terms: tuple[str, ...] = (),
    source_names: tuple[str, ...] = (),
    source_types: tuple[str, ...] = (),
    source_tags: tuple[str, ...] = (),
    source_entities: tuple[str, ...] = (),
    source_breakdown: tuple[str, ...] = (),
    cluster_keys: tuple[str, ...] = (),
    evidence_titles: tuple[str, ...] = (),
    reason_highlights: tuple[str, ...] = (),
    description: str = "Test theme",
) -> Theme:
    """Build a theme row for tests."""
    return Theme(
        canonical_name=canonical_name,
        description=description,
        classification=classification,
        source_count=source_count,
        first_seen_at=TEST_NOW,
        last_seen_at=TEST_NOW,
        momentum_score=momentum_score,
        related_terms=related_terms,
        source_names=source_names,
        source_types=source_types,
        source_tags=source_tags,
        source_entities=source_entities,
        source_breakdown=source_breakdown,
        cluster_keys=cluster_keys,
        evidence_titles=evidence_titles,
        reason_highlights=reason_highlights,
    )


def make_processed_signal(
    *,
    title: str,
    cluster_key: str,
    cluster_terms: tuple[str, ...],
    classification: ItemClassification = ItemClassification.INVESTABLE,
    signal_score: float = 5.0,
    reasons: tuple[str, ...] = (),
    source_name: str = "github",
    source_type: SourceType = SourceType.REPOSITORY,
    tags: tuple[str, ...] = (),
    content_hash: str | None = None,
) -> ProcessedSignal:
    """Build a processed signal row for theme-related tests."""
    item = make_content_item(
        title=title,
        summary=title,
        tags=tags,
        content_hash=content_hash or title.lower().replace(" ", "-"),
        source_name=source_name,
        source_type=source_type,
    )
    return ProcessedSignal(
        item=item,
        cluster_key=cluster_key,
        cluster_terms=cluster_terms,
        classification=classification,
        signal_score=signal_score,
        reasons=reasons,
    )


def make_keyword(
    keyword: str,
    *,
    keyword_type: str = "commercial_term",
    theme_name: str = "Agent Security",
    classification: ItemClassification = ItemClassification.INVESTABLE,
    niche: str = "Tech & AI",
    buyer_type: str = "Developers & AI Startups",
    commercial_score: float = 4.0,
    novelty_score: float = 3.0,
    brandability_score: float = 3.5,
    notes: str = "",
) -> KeywordInsight:
    """Build a keyword insight row for tests."""
    return KeywordInsight(
        keyword=keyword,
        keyword_type=keyword_type,
        theme_name=theme_name,
        classification=classification,
        niche=niche,
        buyer_type=buyer_type,
        commercial_score=commercial_score,
        novelty_score=novelty_score,
        brandability_score=brandability_score,
        notes=notes,
    )


def make_opportunity(
    domain_name: str,
    *,
    extension: str = ".com",
    source_theme: str = "Agent Security",
    recommendation: DomainRecommendation = DomainRecommendation.BUY,
    keyword: str = "agentguard",
    niche: str = "Tech & AI",
    buyer_type: str = "Developers & AI Startups",
    style: str = "premium_compact",
    score: float = 86.0,
    review_bucket: str = "shortlist",
    scoring_profile: str = "startup_brand",
    grade: str = "A",
    value_estimate: str = "$2,500-$5,000",
    rationale: str = "Strong buyer fit.",
    risk_notes: tuple[str, ...] = (),
    rejected_reason: str = "",
) -> DomainOpportunity:
    """Build a domain opportunity row for tests."""
    return DomainOpportunity(
        domain_name=domain_name,
        extension=extension,
        source_theme=source_theme,
        recommendation=recommendation,
        keyword=keyword,
        niche=niche,
        buyer_type=buyer_type,
        style=style,
        score=score,
        review_bucket=review_bucket,
        scoring_profile=scoring_profile,
        grade=grade,
        value_estimate=value_estimate,
        rationale=rationale,
        risk_notes=risk_notes,
        rejected_reason=rejected_reason,
    )
