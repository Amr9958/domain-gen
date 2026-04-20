"""Heuristic first-pass signal classification for Phase 2 processing."""

from __future__ import annotations

from dataclasses import dataclass
import re

from models import ContentItem, ItemClassification, ProcessedSignal, SourceType
from processors.clustering import ClusteredContentItem


INVESTABLE_TERMS = {
    "agent", "agents", "api", "automation", "autonomous", "copilot", "compliance",
    "data", "database", "deployment", "devops", "finops", "inference", "infra",
    "infrastructure", "integration", "monitoring", "observability", "orchestration",
    "payment", "payments", "platform", "privacy", "robotics", "search", "sdk",
    "security", "tooling", "vector", "workflow", "workflows",
}
WATCHLIST_TERMS = {
    "assistant", "benchmark", "beta", "browser", "builder", "cloud", "compiler",
    "dashboard", "engine", "framework", "kernel", "launch", "llm", "model", "release",
    "stack", "studio", "system",
}
SUPPORT_NOISE_TERMS = {
    "bypass", "crack", "download", "installation", "manual", "patch", "serial",
    "support", "unlock", "unlocker", "windows",
}
LOW_VALUE_TERMS = {
    "course", "guide", "list", "newsletter", "opinion", "podcast", "roundup",
    "template", "templates", "thread", "tutorial", "weekly",
}
IGNORE_TERMS = {
    "ask hn", "hiring", "jobs", "layoffs", "lawsuit", "politics", "rant",
    "rumor", "sale", "who is hiring",
}


@dataclass(frozen=True)
class ClassificationResult:
    """The heuristic output used to build a processed signal."""

    classification: ItemClassification
    score: float
    reasons: tuple[str, ...]


def _safe_int(value: object) -> int:
    """Convert collector metrics to integers without crashing the pipeline."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text_blob(item: ContentItem, cluster_terms: tuple[str, ...]) -> str:
    """Build one searchable text blob for keyword heuristics."""
    tags = " ".join(item.tags)
    clusters = " ".join(cluster_terms)
    return f"{item.title} {item.summary} {item.body} {tags} {clusters}".lower()


def _match_terms(text: str, vocabulary: set[str]) -> list[str]:
    """Return matched phrases in a stable order for readable reasons."""
    matches: list[str] = []
    for term in sorted(vocabulary):
        if re.search(rf"\b{re.escape(term)}\b", text):
            matches.append(term)
    return matches


def classify_content_item(
    item: ContentItem,
    cluster_terms: tuple[str, ...] = (),
    *,
    cluster_size: int = 1,
    shared_term_count: int = 0,
    source_diversity: int = 1,
) -> ClassificationResult:
    """Assign an early investability bucket using source, keywords, and traction."""
    text = _text_blob(item, cluster_terms)
    score = 0.0
    reasons: list[str] = []

    if item.source_type in {SourceType.REPOSITORY, SourceType.PRODUCT, SourceType.RELEASE}:
        score += 1.2
        reasons.append("product or repository signal")
    elif item.source_type is SourceType.DEVELOPER:
        score += 0.6
        reasons.append("developer-community signal")
    else:
        score += 0.3

    investable_hits = _match_terms(text, INVESTABLE_TERMS)
    if investable_hits:
        score += min(3.6, 0.9 * len(investable_hits))
        reasons.append(f"commercial terms: {', '.join(investable_hits[:3])}")

    watchlist_hits = _match_terms(text, WATCHLIST_TERMS)
    if watchlist_hits:
        score += min(1.8, 0.45 * len(watchlist_hits))
        reasons.append(f"emerging terms: {', '.join(watchlist_hits[:3])}")

    support_noise_hits = _match_terms(text, SUPPORT_NOISE_TERMS)
    if support_noise_hits:
        score -= min(2.8, 0.85 * len(support_noise_hits))
        reasons.append(f"support / patch phrasing: {', '.join(support_noise_hits[:2])}")

    low_value_hits = _match_terms(text, LOW_VALUE_TERMS)
    if low_value_hits:
        score -= min(2.0, 0.75 * len(low_value_hits))
        reasons.append(f"content-heavy phrasing: {', '.join(low_value_hits[:2])}")

    ignore_hits = _match_terms(text, IGNORE_TERMS)
    if ignore_hits:
        score -= min(3.0, 1.4 * len(ignore_hits))
        reasons.append(f"weak investor intent: {', '.join(ignore_hits[:2])}")

    raw_payload = item.raw_payload if isinstance(item.raw_payload, dict) else {}
    stars = _safe_int(raw_payload.get("stargazers_count"))
    forks = _safe_int(raw_payload.get("forks_count") or raw_payload.get("forks"))
    hn_score = _safe_int(raw_payload.get("score"))
    hn_comments = _safe_int(raw_payload.get("descendants"))

    if stars >= 100:
        score += 2.2
        reasons.append("strong GitHub star velocity")
    elif stars >= 20:
        score += 1.2
        reasons.append("healthy GitHub traction")
    elif stars >= 5:
        score += 0.5

    if forks >= 15:
        score += 0.6

    if hn_score >= 100:
        score += 1.7
        reasons.append("high Hacker News score")
    elif hn_score >= 25:
        score += 0.8

    if hn_comments >= 20:
        score += 0.5

    if len(cluster_terms) >= 2:
        score += 0.35
        reasons.append("clear cluster signature")
    if shared_term_count >= 2:
        score += 0.45
        reasons.append("multiple repeated cluster terms")
    if cluster_size >= 3:
        score += 1.0
        reasons.append("topic repeated across several signals")
    elif cluster_size == 2:
        score += 0.55
        reasons.append("topic repeated across more than one signal")
    if source_diversity >= 2:
        score += 0.75
        reasons.append("confirmed by multiple sources")

    score = round(score, 2)
    if score >= 4.5:
        classification = ItemClassification.INVESTABLE
    elif score >= 2.5:
        classification = ItemClassification.WATCHLIST
    elif score >= 1.0:
        classification = ItemClassification.LOW_VALUE
    else:
        classification = ItemClassification.IGNORE

    return ClassificationResult(
        classification=classification,
        score=score,
        reasons=tuple(reasons[:6]),
    )


def classify_clustered_items(items: list[ClusteredContentItem]) -> list[ProcessedSignal]:
    """Convert clustered items into processed signals with investor-facing labels."""
    processed_items: list[ProcessedSignal] = []
    for clustered in items:
        result = classify_content_item(
            clustered.item,
            clustered.cluster_terms,
            cluster_size=clustered.cluster_size,
            shared_term_count=clustered.shared_term_count,
            source_diversity=clustered.source_diversity,
        )
        processed_items.append(
            ProcessedSignal(
                item=clustered.item,
                cluster_key=clustered.cluster_key,
                cluster_terms=clustered.cluster_terms,
                classification=result.classification,
                signal_score=result.score,
                reasons=result.reasons,
            )
        )
    return processed_items
