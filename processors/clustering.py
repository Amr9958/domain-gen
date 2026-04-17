"""Lightweight clustering for early-stage signal grouping."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from models import ContentItem


STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "about", "your",
    "after", "using", "build", "launch", "open", "source", "tools", "tool", "startup",
    "developer", "developers", "news", "new", "repo", "repository", "app", "data",
}


@dataclass(frozen=True)
class ClusteredContentItem:
    """Processed item decorated with a lightweight cluster key."""

    item: ContentItem
    cluster_key: str
    cluster_terms: tuple[str, ...]


def _extract_terms(item: ContentItem) -> list[str]:
    parts = f"{item.title} {item.summary} {item.body}".split()
    terms = [part for part in parts if len(part) >= 3 and part not in STOP_WORDS]
    return terms


def cluster_processed_items(items: list[ContentItem]) -> list[ClusteredContentItem]:
    """Assign a simple cluster key from the strongest repeated terms."""
    clustered: list[ClusteredContentItem] = []
    for item in items:
        counter = Counter(_extract_terms(item))
        top_terms = tuple(term for term, _ in counter.most_common(3))
        cluster_key = "-".join(top_terms[:2]) if top_terms else "misc"
        clustered.append(
            ClusteredContentItem(
                item=item,
                cluster_key=cluster_key,
                cluster_terms=top_terms,
            )
        )
    return clustered
