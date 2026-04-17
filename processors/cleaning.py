"""Text normalization and cleaning for collected signal items."""

from __future__ import annotations

import re
from dataclasses import replace

from models import ContentItem


WHITESPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^a-z0-9\s\-+/]")


def normalize_text(text: str) -> str:
    """Clean text into a compact analysis-friendly form."""
    lowered = text.strip().lower()
    lowered = NON_WORD_RE.sub(" ", lowered)
    lowered = WHITESPACE_RE.sub(" ", lowered)
    return lowered.strip()


def clean_content_items(items: list[ContentItem]) -> list[ContentItem]:
    """Normalize titles and bodies while preserving original payloads."""
    cleaned: list[ContentItem] = []
    for item in items:
        normalized_title = normalize_text(item.title)
        normalized_summary = normalize_text(item.summary or item.body[:280])
        normalized_body = normalize_text(item.body)
        cleaned.append(
            replace(
                item,
                title=normalized_title or item.title.strip(),
                summary=normalized_summary,
                body=normalized_body,
            )
        )
    return cleaned
