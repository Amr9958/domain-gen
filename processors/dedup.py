"""Deduplication helpers for collected signal items."""

from __future__ import annotations

from models import ContentItem


def deduplicate_content_items(items: list[ContentItem]) -> list[ContentItem]:
    """Remove repeated items using content hash and URL/title fallback keys."""
    deduped: list[ContentItem] = []
    seen_hashes: set[str] = set()
    seen_fallbacks: set[tuple[str, str]] = set()

    for item in items:
        fallback_key = (item.url.strip().lower(), item.title.strip().lower())
        if item.content_hash in seen_hashes or fallback_key in seen_fallbacks:
            continue
        seen_hashes.add(item.content_hash)
        seen_fallbacks.add(fallback_key)
        deduped.append(item)

    return deduped
