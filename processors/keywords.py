"""Keyword intelligence extraction from processed signals and themes."""

from __future__ import annotations

from collections import Counter, defaultdict
import re

from models import ItemClassification, KeywordInsight, ProcessedSignal, SourceType, Theme


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+/\-]{2,}")
KEYWORD_STOP_WORDS = {
    "about", "after", "agentic", "announcing", "around", "article", "articles", "best",
    "build", "building", "built", "code", "community", "developer", "developers", "free",
    "from", "github", "good", "gnews", "guide", "hackernews", "latest", "launch", "launched",
    "more", "news", "open", "opensource", "post", "posts", "project", "projects", "real",
    "repo", "repository", "show", "source", "stack", "story", "stories", "system", "team",
    "teams", "that", "their", "them", "these", "they", "this", "those", "tool", "tools",
    "using", "what", "when", "with", "your",
}
COMMERCIAL_TERMS = {
    "agent", "api", "assistant", "auth", "automation", "billing", "browser", "cloud",
    "compliance", "copilot", "customer", "dashboard", "data", "deploy", "deployment",
    "devops", "edge", "engine", "finops", "fraud", "governance", "infra", "inference",
    "integration", "ledger", "llm", "monitoring", "observability", "ops", "orchestration",
    "payment", "pipeline", "platform", "privacy", "risk", "search", "sdk", "security",
    "storage", "vector", "workflow",
}
NICHE_KEYWORDS = {
    "Tech & AI": {
        "agent", "ai", "api", "assistant", "automation", "cloud", "copilot", "data",
        "deploy", "developer", "devops", "engine", "infra", "inference", "llm", "model",
        "monitoring", "observability", "orchestration", "platform", "sdk", "search",
        "security", "software", "vector", "workflow",
    },
    "Finance & SaaS": {
        "accounting", "banking", "billing", "compliance", "credit", "finance", "fintech",
        "fraud", "invoice", "ledger", "payment", "pricing", "revenue", "risk", "saas",
        "subscription", "tax", "treasury",
    },
    "E-commerce": {
        "brand", "cart", "catalog", "checkout", "commerce", "conversion", "merchant",
        "pricing", "retail", "seller", "shop", "shopping", "store",
    },
    "Creative & Arts": {
        "audio", "canvas", "content", "creator", "design", "image", "media", "music",
        "photo", "render", "studio", "video", "visual",
    },
    "Health & Wellness": {
        "care", "clinic", "doctor", "fitness", "health", "medical", "nutrition",
        "patient", "therapy", "wellness",
    },
    "Real Estate": {
        "broker", "housing", "lease", "listing", "mortgage", "property", "realestate",
        "rental", "tenant",
    },
}
BUYER_HINTS = {
    "Developers & AI Startups": {
        "agent", "ai", "api", "assistant", "builder", "code", "copilot", "developer",
        "devops", "engine", "infra", "llm", "model", "sdk", "security", "workflow",
    },
    "Data & Platform Teams": {
        "analytics", "data", "database", "governance", "infra", "monitoring", "pipeline",
        "platform", "search", "storage", "vector",
    },
    "Fintech Operators": {
        "banking", "billing", "compliance", "finance", "fraud", "invoice", "ledger",
        "payment", "pricing", "risk", "treasury",
    },
    "E-commerce Operators": {
        "cart", "checkout", "commerce", "conversion", "merchant", "retail", "seller",
        "shopping", "store",
    },
    "Creators & Agencies": {
        "audio", "content", "creator", "design", "image", "media", "render", "studio",
        "video", "visual",
    },
    "Health Startups": {
        "care", "clinic", "fitness", "health", "medical", "patient", "therapy", "wellness",
    },
    "Property Operators": {
        "broker", "housing", "lease", "listing", "mortgage", "property", "rental", "tenant",
    },
}
NICHE_FALLBACK_BY_SOURCE = {
    SourceType.REPOSITORY: "Tech & AI",
    SourceType.DEVELOPER: "Tech & AI",
    SourceType.RELEASE: "Tech & AI",
    SourceType.PRODUCT: "Tech & AI",
    SourceType.NEWS: "Tech & AI",
}
BUYER_FALLBACK_BY_NICHE = {
    "Tech & AI": "Developers & AI Startups",
    "Finance & SaaS": "Fintech Operators",
    "E-commerce": "E-commerce Operators",
    "Creative & Arts": "Creators & Agencies",
    "Health & Wellness": "Health Startups",
    "Real Estate": "Property Operators",
}


def _normalize_term(term: str) -> str:
    """Normalize a raw token into a stable keyword term."""
    normalized = term.strip("-+/").lower()
    if normalized.endswith("ies") and len(normalized) > 4:
        return normalized[:-3] + "y"
    if normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _slugify_label(label: str) -> str:
    """Convert a human-readable label into a stable storage-friendly slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower())
    return slug.strip("-")


def _iter_terms(text: str) -> list[str]:
    """Extract normalized keyword candidates from arbitrary text."""
    terms: list[str] = []
    for raw_term in TOKEN_RE.findall(text.lower()):
        term = _normalize_term(raw_term)
        if len(term) < 3 or term.isdigit() or term in KEYWORD_STOP_WORDS:
            continue
        terms.append(term)
    return terms


def _build_theme_term_counter(signals: list[ProcessedSignal], theme: Theme) -> Counter[str]:
    """Aggregate the most representative terms for one theme."""
    counter: Counter[str] = Counter()
    for term in theme.related_terms:
        counter[_normalize_term(term)] += 5

    for signal in signals:
        signal_weight = max(1, int(round(signal.signal_score)))
        weighted_parts = (
            (signal.item.title, 4),
            (signal.item.summary, 2),
            (" ".join(signal.item.tags), 3),
            (signal.item.body[:350], 1),
        )
        for text, weight in weighted_parts:
            for term in _iter_terms(text):
                counter[term] += signal_weight * weight
    return counter


def _brandability_score(term: str) -> float:
    """Estimate whether a term can work as a naming component later."""
    alpha_term = re.sub(r"[^a-z]", "", term.lower())
    if len(alpha_term) < 4 or len(alpha_term) > 11:
        return 0.0

    vowels = sum(character in "aeiou" for character in alpha_term)
    consonants = len(alpha_term) - vowels
    if vowels == 0 or consonants == 0:
        return 0.8

    score = 1.2
    if 4 <= len(alpha_term) <= 8:
        score += 1.6
    if 1 <= vowels <= max(1, len(alpha_term) - 2):
        score += 1.2
    if alpha_term[-1] in "aeioulnrst":
        score += 0.6
    if re.search(r"(.)\1\1", alpha_term):
        score -= 0.7
    return round(max(0.0, min(5.0, score)), 2)


def _commercial_score(term: str, frequency: int, theme: Theme) -> float:
    """Estimate investor/commercial usefulness of a keyword term."""
    score = min(2.4, frequency / 6)
    if term in COMMERCIAL_TERMS:
        score += 1.9
    if term.endswith(("ops", "tech", "flow", "stack", "base", "guard", "grid")):
        score += 0.7
    score += min(1.2, theme.momentum_score / 5)
    return round(max(0.0, min(5.0, score)), 2)


def _novelty_score(term: str, frequency: int) -> float:
    """Estimate how specific and non-generic a term feels."""
    score = 0.6
    if 5 <= len(term) <= 9:
        score += 1.4
    if frequency <= 6:
        score += 1.0
    if term not in COMMERCIAL_TERMS:
        score += 0.8
    if term.endswith(("ly", "ing", "tion")):
        score -= 0.5
    return round(max(0.0, min(5.0, score)), 2)


def _pick_niche(term_counter: Counter[str], signals: list[ProcessedSignal]) -> str:
    """Infer the best niche label from theme terms and source mix."""
    scores: Counter[str] = Counter()
    for niche, vocabulary in NICHE_KEYWORDS.items():
        for term, frequency in term_counter.items():
            if term in vocabulary:
                scores[niche] += frequency

    if scores:
        return scores.most_common(1)[0][0]

    source_counter = Counter(signal.item.source_type for signal in signals)
    if source_counter:
        top_source = source_counter.most_common(1)[0][0]
        return NICHE_FALLBACK_BY_SOURCE.get(top_source, "Tech & AI")
    return "Tech & AI"


def _pick_buyer_type(term_counter: Counter[str], niche: str) -> str:
    """Infer likely buyer persona hints for the keyword set."""
    scores: Counter[str] = Counter()
    for buyer_type, vocabulary in BUYER_HINTS.items():
        for term, frequency in term_counter.items():
            if term in vocabulary:
                scores[buyer_type] += frequency

    if scores:
        return scores.most_common(1)[0][0]
    return BUYER_FALLBACK_BY_NICHE.get(niche, "Developers & AI Startups")


def _select_raw_terms(term_counter: Counter[str]) -> list[str]:
    """Keep the most representative repeated terms for a theme."""
    results: list[str] = []
    for term, _ in term_counter.most_common(6):
        if term not in results:
            results.append(term)
        if len(results) >= 4:
            break
    return results


def _select_commercial_terms(term_counter: Counter[str]) -> list[str]:
    """Extract commercially meaningful terms from the theme context."""
    results: list[str] = []
    for term, _ in term_counter.most_common(12):
        if term in COMMERCIAL_TERMS or term.endswith(("ops", "cloud", "guard", "base", "flow")):
            results.append(term)
        if len(results) >= 4:
            break
    return results


def _select_naming_components(term_counter: Counter[str]) -> list[str]:
    """Extract compact brandable pieces that can feed domain generation later."""
    ranked_terms = sorted(
        term_counter,
        key=lambda term: (_brandability_score(term), term_counter[term], -len(term), term),
        reverse=True,
    )
    results: list[str] = []
    for term in ranked_terms:
        if _brandability_score(term) < 2.8:
            continue
        if not term.isalpha():
            continue
        results.append(term)
        if len(results) >= 4:
            break
    return results


def extract_keyword_insights(
    processed_signals: list[ProcessedSignal],
    themes: list[Theme],
) -> list[KeywordInsight]:
    """Build keyword insights, commercial terms, and buyer hints from themes."""
    signals_by_theme: dict[str, list[ProcessedSignal]] = defaultdict(list)
    for signal in processed_signals:
        if signal.theme_name:
            signals_by_theme[signal.theme_name].append(signal)

    theme_by_name = {theme.canonical_name: theme for theme in themes}
    insights: list[KeywordInsight] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for theme_name, signals in signals_by_theme.items():
        theme = theme_by_name.get(theme_name)
        if theme is None or theme.classification is ItemClassification.IGNORE:
            continue

        term_counter = _build_theme_term_counter(signals, theme)
        if not term_counter:
            continue

        niche = _pick_niche(term_counter, signals)
        buyer_type = _pick_buyer_type(term_counter, niche)
        raw_terms = _select_raw_terms(term_counter)
        commercial_terms = _select_commercial_terms(term_counter)
        naming_components = _select_naming_components(term_counter)

        entries: list[tuple[str, str]] = []
        entries.extend((term, "raw_term") for term in raw_terms)
        entries.extend((term, "commercial_term") for term in commercial_terms)
        entries.extend((term, "naming_component") for term in naming_components)
        entries.append((_slugify_label(niche), "niche_tag"))
        entries.append((_slugify_label(buyer_type), "buyer_hint"))

        for keyword, keyword_type in entries:
            dedupe_key = (theme_name, keyword, keyword_type)
            if dedupe_key in seen_keys or not keyword:
                continue
            seen_keys.add(dedupe_key)

            frequency = term_counter.get(keyword, max(1, theme.source_count))
            commercial_score = _commercial_score(keyword, frequency, theme)
            brandability_score = _brandability_score(keyword)
            novelty_score = _novelty_score(keyword, frequency)

            if keyword_type == "niche_tag":
                notes = f"Inferred niche tag for theme '{theme_name}'."
            elif keyword_type == "buyer_hint":
                notes = f"Inferred buyer hint for theme '{theme_name}'."
            elif keyword_type == "commercial_term":
                notes = f"Inferred commercial term from repeated product language in '{theme_name}'."
            elif keyword_type == "naming_component":
                notes = f"Brandable naming component extracted from theme '{theme_name}'."
            else:
                notes = f"Repeated raw term extracted from theme '{theme_name}'."

            insights.append(
                KeywordInsight(
                    keyword=keyword,
                    keyword_type=keyword_type,
                    theme_name=theme_name,
                    classification=theme.classification,
                    niche=niche,
                    buyer_type=buyer_type,
                    commercial_score=commercial_score,
                    novelty_score=novelty_score,
                    brandability_score=brandability_score,
                    notes=notes,
                )
            )

    insights.sort(
        key=lambda insight: (
            insight.commercial_score,
            insight.brandability_score,
            insight.novelty_score,
            insight.theme_name,
        ),
        reverse=True,
    )
    return insights
