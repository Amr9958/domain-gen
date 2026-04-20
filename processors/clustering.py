"""Lightweight clustering for early-stage signal grouping."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from models import ContentItem


STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "about", "your",
    "after", "using", "build", "launch", "open", "source", "tools", "tool", "startup",
    "developer", "developers", "news", "new", "repo", "repository", "app", "data",
    "project", "projects", "code", "coding", "software", "team", "teams", "post",
    "posts", "article", "articles", "story", "stories", "show", "ask", "best",
    "good", "great", "latest", "top", "free", "github", "hackernews", "gnews",
}
GENERIC_CLUSTER_TERMS = {
    "application", "app", "feature", "framework", "guide", "latest", "library",
    "platform", "release", "service", "solution", "support", "system", "update",
}
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+/\-]{2,}")


@dataclass(frozen=True)
class ClusteredContentItem:
    """Processed item decorated with a lightweight cluster key."""

    item: ContentItem
    cluster_key: str
    cluster_terms: tuple[str, ...]
    cluster_size: int = 1
    shared_term_count: int = 0
    source_diversity: int = 1


def _normalize_term(term: str) -> str:
    """Collapse minor plural variations so cluster keys stay more stable."""
    normalized = term.strip("-+/").lower()
    if normalized.endswith("ies") and len(normalized) > 4:
        return normalized[:-3] + "y"
    if normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _extract_weighted_terms(item: ContentItem) -> Counter[str]:
    """Weight title and tag terms higher than body text for better grouping."""
    counter: Counter[str] = Counter()
    weighted_parts = (
        (item.title, 4),
        (item.summary, 2),
        (item.body, 1),
        (" ".join(item.tags), 3),
    )
    for text, weight in weighted_parts:
        terms: list[str] = []
        for match in TOKEN_RE.findall(text.lower()):
            term = _normalize_term(match)
            if len(term) < 3 or term in STOP_WORDS:
                continue
            terms.append(term)
            counter[term] += weight

        # Repeated 2-word compounds produce stronger cluster signatures than
        # isolated generic tokens such as "platform" or "system".
        for left, right in zip(terms, terms[1:]):
            if left == right:
                continue
            if left in GENERIC_CLUSTER_TERMS and right in GENERIC_CLUSTER_TERMS:
                continue
            counter[f"{left}-{right}"] += max(1, weight - 1)
    return counter


def _rank_terms(local_terms: Counter[str], global_frequency: Counter[str]) -> tuple[str, ...]:
    """Prefer terms that are locally strong and repeated across more than one item."""
    if not local_terms:
        return ()

    shared_terms = [term for term in local_terms if global_frequency[term] >= 2]
    ranked_pool = shared_terms or list(local_terms)
    ranked_terms = sorted(
        ranked_pool,
        key=lambda term: (
            global_frequency[term],
            1 if "-" in term else 0,
            0 if term in GENERIC_CLUSTER_TERMS else 1,
            local_terms[term],
            len(term),
            term,
        ),
        reverse=True,
    )
    selected_terms: list[str] = []
    covered_atoms: set[str] = set()
    for term in ranked_terms:
        atoms = set(term.split("-"))
        if atoms and atoms <= covered_atoms:
            continue
        selected_terms.append(term)
        covered_atoms.update(atoms)
        if len(selected_terms) >= 3:
            break
    return tuple(selected_terms)


def _build_cluster_key(source_type_value: str, top_terms: tuple[str, ...]) -> str:
    """Build a stable cluster key while avoiding unrelated trailing terms."""
    if not top_terms:
        return f"{source_type_value}-misc"

    leading_term = top_terms[0]
    if len(top_terms) == 1:
        return f"{source_type_value}-{leading_term}"

    leading_atoms = set(leading_term.split("-"))
    second_term = top_terms[1]
    second_atoms = set(second_term.split("-"))
    if "-" in leading_term and not (leading_atoms & second_atoms):
        return f"{source_type_value}-{leading_term}"
    return "-".join(top_terms[:2])


def cluster_processed_items(items: list[ContentItem]) -> list[ClusteredContentItem]:
    """Assign a cluster key using weighted item terms and corpus-wide repeats."""
    clustered: list[ClusteredContentItem] = []
    global_frequency: Counter[str] = Counter()
    local_term_map: dict[str, Counter[str]] = {}

    for item in items:
        weighted_terms = _extract_weighted_terms(item)
        local_term_map[item.content_hash] = weighted_terms
        global_frequency.update(weighted_terms.keys())

    provisional_rows: list[tuple[ContentItem, str, tuple[str, ...]]] = []
    cluster_sizes: Counter[str] = Counter()
    cluster_sources: dict[str, set[str]] = {}

    for item in items:
        top_terms = _rank_terms(local_term_map.get(item.content_hash, Counter()), global_frequency)
        cluster_key = _build_cluster_key(item.source_type.value, top_terms)
        provisional_rows.append((item, cluster_key, top_terms))
        cluster_sizes[cluster_key] += 1
        cluster_sources.setdefault(cluster_key, set()).add(item.source_name)

    for item, cluster_key, top_terms in provisional_rows:
        shared_term_count = sum(1 for term in top_terms if global_frequency[term] >= 2)
        clustered.append(
            ClusteredContentItem(
                item=item,
                cluster_key=cluster_key,
                cluster_terms=top_terms,
                cluster_size=cluster_sizes[cluster_key],
                shared_term_count=shared_term_count,
                source_diversity=len(cluster_sources.get(cluster_key, {item.source_name})),
            )
        )
    return clustered
