"""Theme extraction helpers built on top of classified processed signals."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
import re

from models import ItemClassification, ProcessedSignal, Theme


CLASSIFICATION_PRIORITY = {
    ItemClassification.IGNORE: 0,
    ItemClassification.LOW_VALUE: 1,
    ItemClassification.WATCHLIST: 2,
    ItemClassification.INVESTABLE: 3,
}
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+/\-]{2,}")
THEME_STOP_WORDS = {
    "about", "after", "and", "announcing", "around", "build", "building", "code",
    "data", "developer", "developers", "for", "from", "github", "guide", "gnews",
    "hackernews", "launch", "latest", "more", "news", "open", "project", "projects",
    "repo", "repository", "show", "source", "startup", "story", "stories", "system",
    "team", "teams", "that", "the", "their", "these", "this", "tool", "tools", "using",
    "with",
}
ENTITY_STOP_WORDS = THEME_STOP_WORDS | {
    "agent", "ai", "api", "app", "assistant", "automation", "cloud", "data", "engine",
    "framework", "health", "infra", "library", "model", "multiagent", "openai", "orchestration",
    "platform", "product", "sdk", "security", "service", "software", "stack", "system",
    "tooling", "toolkit", "workflow",
}
NORMALIZED_ENTITY_STOP_WORDS = {re.sub(r"[^a-z0-9]", "", term) for term in ENTITY_STOP_WORDS}


@dataclass
class _ThemeBucket:
    """Internal consolidation bucket for new signals and optional historical themes."""

    canonical_name: str
    signature_terms: set[str]
    signals: list[ProcessedSignal] = field(default_factory=list)
    existing_theme: Theme | None = None


def _normalize_term(term: str) -> str:
    """Normalize theme terms so cross-run merges are more stable."""
    normalized = term.strip("-+/").lower()
    if normalized.endswith("ies") and len(normalized) > 4:
        return normalized[:-3] + "y"
    if normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _iter_terms(text: str) -> list[str]:
    """Extract normalized theme terms from arbitrary source text."""
    terms: list[str] = []
    for raw_term in TOKEN_RE.findall(text.lower()):
        term = _normalize_term(raw_term)
        if len(term) < 3 or term in THEME_STOP_WORDS:
            continue
        terms.append(term)
    return terms


def _theme_term_counter(signals: list[ProcessedSignal], existing_theme: Theme | None = None) -> Counter[str]:
    """Build a representative term counter for one theme bucket."""
    counter: Counter[str] = Counter()
    if existing_theme is not None:
        historical_weight = max(3, min(8, existing_theme.source_count))
        for term in existing_theme.related_terms:
            counter[_normalize_term(term)] += historical_weight
        for term in _iter_terms(existing_theme.canonical_name):
            counter[term] += historical_weight

    for signal in signals:
        signal_weight = max(1, int(round(signal.signal_score)))
        for term in signal.cluster_terms:
            counter[_normalize_term(term)] += signal_weight * 4
        for term in _iter_terms(signal.item.title):
            counter[term] += signal_weight * 2
        for term in _iter_terms(signal.item.summary):
            counter[term] += signal_weight
        for tag in signal.item.tags:
            for term in _iter_terms(tag):
                counter[term] += signal_weight * 2
    return counter


def _theme_name(signals: list[ProcessedSignal], term_counter: Counter[str]) -> tuple[str, tuple[str, ...]]:
    """Create a stable human-readable theme name from dominant terms."""
    related_terms = tuple(term for term, _ in term_counter.most_common(6))
    display_terms: list[str] = []
    covered_atoms: set[str] = set()
    for term in related_terms:
        atoms = {atom for atom in term.split("-") if atom}
        if atoms and atoms <= covered_atoms:
            continue
        display_terms.append(term.replace("-", " ").title())
        covered_atoms.update(atoms)
        if len(display_terms) >= 2:
            break

    if display_terms:
        canonical_name = display_terms[0] if " " in display_terms[0] else " ".join(display_terms[:2])
    elif signals:
        canonical_name = signals[0].cluster_key.replace("-", " ").title()
    else:
        canonical_name = "Misc Signals"
    return canonical_name, related_terms


def _theme_classification(signals: list[ProcessedSignal], existing_theme: Theme | None = None) -> ItemClassification:
    """Promote a cluster based on average signal quality and strongest members."""
    average_score = sum(signal.signal_score for signal in signals) / max(len(signals), 1)
    best_rank = max(CLASSIFICATION_PRIORITY[signal.classification] for signal in signals)
    if existing_theme is not None:
        best_rank = max(best_rank, CLASSIFICATION_PRIORITY[existing_theme.classification])
        average_score = max(average_score, existing_theme.momentum_score * 0.7)

    if average_score >= 4.0 or best_rank >= CLASSIFICATION_PRIORITY[ItemClassification.INVESTABLE]:
        return ItemClassification.INVESTABLE
    if average_score >= 2.4 or best_rank >= CLASSIFICATION_PRIORITY[ItemClassification.WATCHLIST]:
        return ItemClassification.WATCHLIST
    if average_score >= 1.0:
        return ItemClassification.LOW_VALUE
    return ItemClassification.IGNORE


def _signature_terms_for_theme(theme: Theme) -> set[str]:
    """Build a matching signature from a historical theme snapshot."""
    signature_terms = {_normalize_term(term) for term in theme.related_terms if _normalize_term(term)}
    signature_terms.update(_iter_terms(theme.canonical_name))
    return signature_terms


def _signature_terms_for_signals(signals: list[ProcessedSignal]) -> set[str]:
    """Build a compact signature for one new cluster of signals."""
    term_counter = _theme_term_counter(signals)
    return {term for term, _ in term_counter.most_common(6)}


def _signature_atoms(terms: set[str]) -> set[str]:
    """Explode compound terms so related clusters can merge by shared atoms."""
    atoms: set[str] = set()
    for term in terms:
        for atom in term.split("-"):
            normalized = _normalize_term(atom)
            if len(normalized) < 3 or normalized in THEME_STOP_WORDS:
                continue
            atoms.add(normalized)
    return atoms


def _bucket_match_score(bucket_terms: set[str], candidate_terms: set[str]) -> float:
    """Estimate whether a cluster belongs to an existing theme bucket."""
    if not bucket_terms or not candidate_terms:
        return 0.0
    shared_terms = bucket_terms & candidate_terms
    direct_jaccard = len(shared_terms) / max(len(bucket_terms | candidate_terms), 1)
    if len(shared_terms) >= 2:
        return 1.2 + len(shared_terms) + direct_jaccard
    if direct_jaccard >= 0.34:
        return 1.1 + direct_jaccard

    bucket_atoms = _signature_atoms(bucket_terms)
    candidate_atoms = _signature_atoms(candidate_terms)
    shared_atoms = bucket_atoms & candidate_atoms
    if not shared_atoms:
        return 0.0

    atom_jaccard = len(shared_atoms) / max(len(bucket_atoms | candidate_atoms), 1)
    if len(shared_atoms) >= 3:
        return 1.15 + atom_jaccard + min(0.35, 0.08 * len(shared_atoms))
    if len(shared_atoms) >= 2 and atom_jaccard >= 0.34:
        return 1.0 + atom_jaccard
    return 0.0


def _build_theme_description(
    classification: ItemClassification,
    source_count: int,
    source_breakdown: tuple[str, ...],
    source_types: tuple[str, ...],
    related_terms: tuple[str, ...],
    reason_highlights: tuple[str, ...],
    evidence_titles: tuple[str, ...],
    existing_theme: Theme | None = None,
) -> str:
    """Create a readable theme summary with lightweight source tagging."""
    top_sources = ", ".join(source_breakdown[:3]) if source_breakdown else "unknown sources"
    typed_sources = ", ".join(source_types[:2]) if source_types else "mixed sources"
    leading_terms = ", ".join(term.replace("-", " ") for term in related_terms[:3]) if related_terms else "mixed terms"
    description = (
        f"{classification.value.replace('_', ' ').title()} theme supported by "
        f"{source_count} signals with {typed_sources} coverage. "
        f"Leading terms: {leading_terms}. "
        f"Source mix: {top_sources}."
    )
    if reason_highlights:
        description += f" Strongest reasons: {', '.join(reason_highlights[:2])}."
    if evidence_titles:
        description += f" Example signals: {', '.join(evidence_titles[:2])}."
    if existing_theme is not None:
        description += " Consolidated with a previous run to keep theme naming stable."
    return description


def _extract_source_entity_candidates(signal: ProcessedSignal) -> list[str]:
    """Extract compact source-specific identifiers useful for later risk checks."""
    candidates: list[str] = []
    raw_payload = signal.item.raw_payload if isinstance(signal.item.raw_payload, dict) else {}

    repo_full_name = str(raw_payload.get("full_name") or "").strip().lower()
    if repo_full_name and "/" in repo_full_name:
        candidates.append(repo_full_name.rsplit("/", 1)[-1])

    for raw_value in (
        raw_payload.get("name"),
        raw_payload.get("title"),
        signal.item.title,
    ):
        text = str(raw_value or "").strip().lower()
        if not text:
            continue
        terms = [
            term
            for term in _iter_terms(text)
            if re.sub(r"[^a-z0-9]", "", term) not in NORMALIZED_ENTITY_STOP_WORDS
        ]
        if 1 <= len(terms) <= 2:
            collapsed = "".join(terms)
            if len(collapsed) >= 5:
                candidates.append(collapsed)
        for term in terms[:3]:
            if len(term) >= 5 and term not in ENTITY_STOP_WORDS:
                candidates.append(term)

    ordered_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = re.sub(r"[^a-z0-9]", "", candidate)
        if len(normalized) < 5 or normalized in seen:
            continue
        seen.add(normalized)
        ordered_candidates.append(normalized)
    return ordered_candidates[:5]


def _seed_counter_from_breakdown(entries: tuple[str, ...]) -> Counter[str]:
    """Parse persisted breakdown strings like 'github x3' back into counts."""
    counter: Counter[str] = Counter()
    for entry in entries:
        text = entry.strip()
        if not text:
            continue
        if " x" in text:
            name, _, raw_count = text.rpartition(" x")
            try:
                counter[name.strip()] += int(raw_count)
                continue
            except ValueError:
                pass
        counter[text] += 1
    return counter


def _collect_source_metadata(
    signals: list[ProcessedSignal],
    existing_theme: Theme | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Build structured source tagging for a theme from signals plus historical metadata."""
    source_name_counter: Counter[str] = Counter(existing_theme.source_names if existing_theme else ())
    source_type_counter: Counter[str] = Counter(existing_theme.source_types if existing_theme else ())
    source_tag_counter: Counter[str] = Counter(existing_theme.source_tags if existing_theme else ())
    source_entity_counter: Counter[str] = Counter(existing_theme.source_entities if existing_theme else ())
    source_breakdown_counter = _seed_counter_from_breakdown(existing_theme.source_breakdown if existing_theme else ())

    for signal in signals:
        source_name_counter[signal.item.source_name] += 1
        source_type_counter[str(signal.item.source_type.value)] += 1
        source_breakdown_counter[signal.item.source_name] += 1
        for tag in signal.item.tags:
            normalized_tag = _normalize_term(tag)
            if normalized_tag and normalized_tag not in THEME_STOP_WORDS:
                source_tag_counter[normalized_tag] += 1
        for entity in _extract_source_entity_candidates(signal):
            source_entity_counter[entity] += 1

    source_names = tuple(name for name, _ in source_name_counter.most_common(5))
    source_types = tuple(source_type for source_type, _ in source_type_counter.most_common(4))
    source_tags = tuple(tag for tag, _ in source_tag_counter.most_common(6))
    source_entities = tuple(entity for entity, _ in source_entity_counter.most_common(6))
    source_breakdown = tuple(f"{name} x{count}" for name, count in source_breakdown_counter.most_common(5))
    return source_names, source_types, source_tags, source_entities, source_breakdown


def _collect_cluster_keys(signals: list[ProcessedSignal], existing_theme: Theme | None = None) -> tuple[str, ...]:
    """Collect the most representative raw cluster keys for debugging and review."""
    cluster_counter: Counter[str] = Counter(existing_theme.cluster_keys if existing_theme else ())
    for signal in signals:
        if signal.cluster_key:
            cluster_counter[signal.cluster_key] += 1
    return tuple(cluster_key for cluster_key, _ in cluster_counter.most_common(6))


def _collect_evidence_titles(signals: list[ProcessedSignal], existing_theme: Theme | None = None) -> tuple[str, ...]:
    """Keep a few concrete signal titles that explain why this theme exists."""
    titles: list[str] = list(existing_theme.evidence_titles if existing_theme else ())
    seen_titles = {title.strip().lower() for title in titles if title.strip()}
    for signal in sorted(signals, key=lambda item: item.signal_score, reverse=True):
        title = signal.item.title.strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        titles.append(title)
        if len(titles) >= 4:
            break
    return tuple(titles[:4])


def _collect_reason_highlights(signals: list[ProcessedSignal], existing_theme: Theme | None = None) -> tuple[str, ...]:
    """Aggregate the strongest classifier reasons into readable theme evidence."""
    counter: Counter[str] = Counter(existing_theme.reason_highlights if existing_theme else ())
    for signal in signals:
        for reason in signal.reasons:
            normalized_reason = reason.strip()
            if normalized_reason:
                counter[normalized_reason] += 1
    return tuple(reason for reason, _ in counter.most_common(5))


def _consolidate_signal_groups(
    grouped_signals: dict[str, list[ProcessedSignal]],
    existing_themes: list[Theme],
) -> list[_ThemeBucket]:
    """Merge close clusters together and align them with historical themes when possible."""
    buckets: list[_ThemeBucket] = [
        _ThemeBucket(
            canonical_name=theme.canonical_name,
            signature_terms=_signature_terms_for_theme(theme),
            existing_theme=theme,
        )
        for theme in existing_themes
    ]

    ordered_groups = sorted(
        grouped_signals.values(),
        key=lambda signals: (
            len(signals),
            max((signal.signal_score for signal in signals), default=0.0),
        ),
        reverse=True,
    )

    for cluster_signals in ordered_groups:
        signature_terms = _signature_terms_for_signals(cluster_signals)
        if not signature_terms:
            signature_terms = {_normalize_term(signal.cluster_key) for signal in cluster_signals if signal.cluster_key}

        best_bucket: _ThemeBucket | None = None
        best_score = 0.0
        for bucket in buckets:
            match_score = _bucket_match_score(bucket.signature_terms, signature_terms)
            if match_score > best_score:
                best_score = match_score
                best_bucket = bucket

        if best_bucket is not None and best_score >= 1.15:
            best_bucket.signals.extend(cluster_signals)
            best_bucket.signature_terms.update(signature_terms)
            continue

        provisional_name, _ = _theme_name(cluster_signals, _theme_term_counter(cluster_signals))
        buckets.append(
            _ThemeBucket(
                canonical_name=provisional_name,
                signature_terms=set(signature_terms),
                signals=list(cluster_signals),
            )
        )

    return [bucket for bucket in buckets if bucket.signals]


def build_themes(
    signals: list[ProcessedSignal],
    existing_themes: list[Theme] | None = None,
) -> tuple[list[ProcessedSignal], list[Theme]]:
    """Group processed signals into consolidated themes and attach the theme metadata."""
    grouped: dict[str, list[ProcessedSignal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.cluster_key].append(signal)

    themed_signals: list[ProcessedSignal] = []
    themes: list[Theme] = []
    buckets = _consolidate_signal_groups(grouped, existing_themes or [])

    for bucket in buckets:
        term_counter = _theme_term_counter(bucket.signals, bucket.existing_theme)
        generated_name, related_terms = _theme_name(bucket.signals, term_counter)
        canonical_name = bucket.existing_theme.canonical_name if bucket.existing_theme is not None else generated_name
        classification = _theme_classification(bucket.signals, bucket.existing_theme)
        first_seen_at = min(
            (signal.item.published_at or signal.item.fetched_at) for signal in bucket.signals
        )
        last_seen_at = max(
            (signal.item.published_at or signal.item.fetched_at) for signal in bucket.signals
        )
        source_names = {signal.item.source_name for signal in bucket.signals}
        average_score = sum(signal.signal_score for signal in bucket.signals) / max(len(bucket.signals), 1)
        (
            structured_source_names,
            structured_source_types,
            source_tags,
            source_entities,
            source_breakdown,
        ) = _collect_source_metadata(
            bucket.signals,
            bucket.existing_theme,
        )
        cluster_keys = _collect_cluster_keys(bucket.signals, bucket.existing_theme)
        evidence_titles = _collect_evidence_titles(bucket.signals, bucket.existing_theme)
        reason_highlights = _collect_reason_highlights(bucket.signals, bucket.existing_theme)

        if bucket.existing_theme is not None:
            first_seen_at = min(first_seen_at, bucket.existing_theme.first_seen_at)
            last_seen_at = max(last_seen_at, bucket.existing_theme.last_seen_at)
            source_count = bucket.existing_theme.source_count + len(bucket.signals)
            historical_bonus = min(bucket.existing_theme.source_count / 10, 2.0)
            momentum_score = round(
                max(
                    average_score + (0.35 * len(source_names)) + historical_bonus,
                    (bucket.existing_theme.momentum_score * 0.6) + average_score,
                ),
                2,
            )
        else:
            source_count = len(bucket.signals)
            momentum_score = round(average_score + (0.35 * len(source_names)), 2)

        description = _build_theme_description(
            classification,
            source_count,
            source_breakdown,
            structured_source_types,
            related_terms,
            reason_highlights,
            evidence_titles,
            existing_theme=bucket.existing_theme,
        )

        theme = Theme(
            canonical_name=canonical_name,
            description=description,
            classification=classification,
            source_count=source_count,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            momentum_score=momentum_score,
            related_terms=related_terms,
            source_names=structured_source_names,
            source_types=structured_source_types,
            source_tags=source_tags,
            source_entities=source_entities,
            source_breakdown=source_breakdown,
            cluster_keys=cluster_keys,
            evidence_titles=evidence_titles,
            reason_highlights=reason_highlights,
        )
        themes.append(theme)

        for signal in bucket.signals:
            themed_signals.append(
                replace(
                    signal,
                    theme_name=canonical_name,
                    theme_description=description,
                )
            )

    themes.sort(key=lambda theme: (theme.momentum_score, theme.source_count), reverse=True)
    themed_signals.sort(key=lambda signal: (signal.signal_score, signal.theme_name), reverse=True)
    return themed_signals, themes
