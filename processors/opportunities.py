"""Domain opportunity generation from keyword insights and trend themes."""

from __future__ import annotations

from collections import defaultdict
import random
import re

from generator import generate_domains
from models import DomainOpportunity, DomainRecommendation, ItemClassification, KeywordInsight, Theme
from scoring import evaluate_domain
from scoring.hard_filters import TRADEMARK_TERMS
from scoring.scoring import grade_from_score, resale_tier_from_grade
from utils.word_banks import load_word_banks


KEYWORD_TYPE_PRIORITY = {
    "commercial_term": 0,
    "naming_component": 1,
    "raw_term": 2,
    "niche_tag": 3,
    "buyer_hint": 4,
}
AI_SIGNAL_TERMS = {"agent", "ai", "assistant", "automation", "copilot", "inference", "llm", "model", "vector"}
SEO_SERVICE_TERMS = {
    "care", "cleaning", "clinic", "dental", "health", "home", "homes", "legal", "medical",
    "property", "realty", "repair", "roof", "roofing", "tax",
}
PROFILE_BY_NICHE = {
    "Tech & AI": "startup_brand",
    "Finance & SaaS": "flip_fast",
    "E-commerce": "startup_brand",
    "Creative & Arts": "startup_brand",
    "Health & Wellness": "startup_brand",
    "Real Estate": "seo_exact",
}
PROFILE_EXTENSIONS = {
    "ai_brand": [".com", ".ai", ".io"],
    "startup_brand": [".com", ".ai", ".io"],
    "flip_fast": [".com", ".io", ".co"],
    "geo_local": [".com", ".co"],
    "seo_exact": [".com", ".net"],
}
RECOMMENDATION_RANK = {
    DomainRecommendation.BUY: 2,
    DomainRecommendation.WATCH: 1,
    DomainRecommendation.SKIP: 0,
}
REVIEW_BUCKET_RANK = {
    "shortlist": 2,
    "watchlist": 1,
    "rejected": 0,
}
DESCRIPTIVE_SUFFIXES_BY_NICHE = {
    "Tech & AI": ("hq", "labs", "ops", "stack", "flow", "guard", "base", "pilot"),
    "Finance & SaaS": ("pay", "ledger", "risk", "fund", "vault", "flow", "desk"),
    "E-commerce": ("shop", "cart", "store", "supply", "market", "stack"),
    "Creative & Arts": ("studio", "works", "craft", "forge", "canvas", "labs"),
    "Health & Wellness": ("care", "clinic", "health", "well", "labs"),
    "Real Estate": ("home", "realty", "lease", "property", "roof", "broker"),
}
BAD_CANDIDATE_TERMS = {
    "blog", "course", "guide", "list", "news", "newsletter", "podcast", "template", "tutorial",
}
GENERIC_SOURCE_ENTITY_TERMS = AI_SIGNAL_TERMS | SEO_SERVICE_TERMS | {
    "auth", "base", "care", "cloud", "data", "flow", "guard", "health", "home", "hq",
    "infra", "labs", "ledger", "library", "model", "multiagent", "ops", "orchestration",
    "pay", "pilot", "platform", "property", "realty", "risk", "search", "security", "stack",
    "store", "studio", "toolkit", "vault", "well", "workflow", *BAD_CANDIDATE_TERMS,
}
TOKEN_RE = re.compile(r"[^a-z]")


def _group_keywords_by_theme(keywords: list[KeywordInsight]) -> dict[str, list[KeywordInsight]]:
    """Group keyword insights by theme name for focused generation."""
    grouped: dict[str, list[KeywordInsight]] = defaultdict(list)
    for keyword in keywords:
        grouped[keyword.theme_name].append(keyword)
    return grouped


def _keyword_priority(keyword: KeywordInsight) -> tuple[float, float, float, int, str]:
    """Rank keyword insights by commercial usefulness and naming value."""
    return (
        keyword.commercial_score,
        keyword.brandability_score,
        keyword.novelty_score,
        -KEYWORD_TYPE_PRIORITY.get(keyword.keyword_type, 99),
        keyword.keyword,
    )


def _select_seed_keywords(keywords: list[KeywordInsight]) -> list[KeywordInsight]:
    """Choose the strongest unique keyword seeds for one theme."""
    ordered = sorted(keywords, key=_keyword_priority, reverse=True)
    selected: list[KeywordInsight] = []
    seen: set[str] = set()
    for keyword in ordered:
        if keyword.keyword_type in {"niche_tag", "buyer_hint"}:
            continue
        if keyword.keyword in seen:
            continue
        seen.add(keyword.keyword)
        selected.append(keyword)
        if len(selected) >= 4:
            break
    return selected


def _pick_niche(keywords: list[KeywordInsight]) -> str:
    """Prefer the most common explicit niche across keyword insights."""
    for keyword in sorted(keywords, key=_keyword_priority, reverse=True):
        if keyword.niche:
            return keyword.niche
    return "Tech & AI"


def _pick_buyer_type(keywords: list[KeywordInsight]) -> str:
    """Prefer the strongest inferred buyer type from keyword insights."""
    for keyword in sorted(keywords, key=_keyword_priority, reverse=True):
        if keyword.buyer_type:
            return keyword.buyer_type
    return "Developers & AI Startups"


def _choose_profile(theme: Theme, seed_keywords: list[KeywordInsight], niche: str) -> str:
    """Map a theme and its strongest keywords to a scoring profile."""
    seed_terms = {keyword.keyword for keyword in seed_keywords} | set(theme.related_terms)
    if niche == "Tech & AI" and seed_terms & AI_SIGNAL_TERMS:
        return "ai_brand"
    if niche in {"Health & Wellness", "Real Estate"} and seed_terms & SEO_SERVICE_TERMS:
        return "seo_exact"
    if theme.classification is ItemClassification.LOW_VALUE and niche == "Finance & SaaS":
        return "seo_exact"
    return PROFILE_BY_NICHE.get(niche, "startup_brand")


def _choose_extensions(profile: str, niche: str) -> list[str]:
    """Choose a short extension list so the shortlist stays focused."""
    extensions = PROFILE_EXTENSIONS.get(profile, [".com", ".ai"])
    if niche not in {"Tech & AI", "Finance & SaaS"}:
        extensions = [extension for extension in extensions if extension != ".ai"] or extensions
    return extensions[:3]


def _normalize_candidate_name(name: str) -> str:
    """Normalize raw candidate text into a compact base name."""
    return TOKEN_RE.sub("", name.lower())


def _merge_name_parts(left: str, right: str) -> str:
    """Join two normalized parts while trimming obvious overlap."""
    left = _normalize_candidate_name(left)
    right = _normalize_candidate_name(right)
    if not left:
        return right
    if not right:
        return left
    if left[-1] == right[0]:
        return left + right[1:]
    return left + right


def _is_promising_candidate_name(name: str) -> bool:
    """Reject obviously weak descriptive names before spending scoring work."""
    if len(name) < 4 or len(name) > 16:
        return False
    if any(term in name for term in BAD_CANDIDATE_TERMS):
        return False
    if re.search(r"(.)\1\1", name):
        return False
    if len(name) >= 10 and len(set(name)) <= 4:
        return False
    if len(name) % 2 == 0 and name[: len(name) // 2] == name[len(name) // 2 :]:
        return False
    return True


def _append_candidate(
    candidates: dict[str, dict[str, str | bool]],
    raw_name: str,
    method: str,
    source_name: str = "",
) -> None:
    """Add a normalized opportunity candidate if it clears quality checks."""
    clean_name = _normalize_candidate_name(raw_name)
    if not _is_promising_candidate_name(clean_name):
        return
    if clean_name not in candidates:
        candidates[clean_name] = {
            "name": clean_name,
            "method": method,
            "source_name": _normalize_candidate_name(source_name),
            "is_transformed": bool(source_name and _normalize_candidate_name(source_name) != clean_name),
        }


def _deterministic_generate_candidates(
    theme_name: str,
    niche: str,
    seed_keywords: list[str],
    word_banks: dict[str, list[str]],
) -> list[dict[str, str | bool]]:
    """Generate repeatable candidates by temporarily seeding the shared generator."""
    random_state = random.getstate()
    random.seed(f"{theme_name}|{','.join(seed_keywords)}")
    try:
        return generate_domains(
            niche=niche,
            use_llm=False,
            word_banks=word_banks,
            keywords_str=", ".join(seed_keywords),
            num_per_tier=8,
        )
    finally:
        random.setstate(random_state)


def _build_supplemental_candidates(
    theme_name: str,
    niche: str,
    seed_keywords: list[KeywordInsight],
    theme_keywords: list[KeywordInsight],
) -> list[dict[str, str | bool]]:
    """Generate extra deterministic candidates tailored to trend-derived themes."""
    _ = theme_name
    candidates: dict[str, dict[str, str | bool]] = {}
    seed_terms = [keyword.keyword for keyword in seed_keywords if keyword.keyword]
    commercial_terms = [
        keyword.keyword for keyword in theme_keywords if keyword.keyword_type == "commercial_term" and keyword.keyword
    ]
    naming_components = [
        keyword.keyword for keyword in theme_keywords if keyword.keyword_type == "naming_component" and keyword.keyword
    ]
    raw_terms = [keyword.keyword for keyword in theme_keywords if keyword.keyword_type == "raw_term" and keyword.keyword]
    suffixes = DESCRIPTIVE_SUFFIXES_BY_NICHE.get(niche, ("labs", "works", "flow", "stack"))

    for keyword in seed_terms[:3]:
        _append_candidate(candidates, keyword, "exact")
        for suffix in suffixes[:3]:
            _append_candidate(candidates, _merge_name_parts(keyword, suffix), "descriptive", source_name=keyword)

    for commercial in commercial_terms[:3]:
        for naming in naming_components[:3]:
            _append_candidate(candidates, _merge_name_parts(naming, commercial), "theme_blend", source_name=naming)
            _append_candidate(candidates, _merge_name_parts(commercial, naming), "theme_blend", source_name=commercial)

    for left_index, left in enumerate(naming_components[:3]):
        for right in naming_components[left_index + 1 : 4]:
            _append_candidate(candidates, _merge_name_parts(left, right), "premium_compact", source_name=left)

    for raw_term in raw_terms[:2]:
        for commercial in commercial_terms[:2]:
            _append_candidate(candidates, _merge_name_parts(raw_term, commercial), "exact_match", source_name=raw_term)

    return list(candidates.values())


def _recommendation_from_appraisal(
    appraisal_score: int,
    theme: Theme,
    average_commercial_score: float,
    warnings: tuple[str, ...],
    rejected: bool,
) -> DomainRecommendation:
    """Convert scorer output into investor-facing buy/watch/skip guidance."""
    if rejected or appraisal_score < 55:
        recommendation = DomainRecommendation.SKIP
    elif appraisal_score >= 80:
        recommendation = DomainRecommendation.BUY
    elif appraisal_score >= 65:
        recommendation = DomainRecommendation.WATCH
    else:
        recommendation = DomainRecommendation.SKIP

    if theme.classification is ItemClassification.WATCHLIST and recommendation is DomainRecommendation.BUY:
        recommendation = DomainRecommendation.WATCH
    if theme.classification is ItemClassification.LOW_VALUE and recommendation is not DomainRecommendation.SKIP:
        recommendation = DomainRecommendation.SKIP
    if average_commercial_score < 3.0 and recommendation is DomainRecommendation.BUY:
        recommendation = DomainRecommendation.WATCH
    if any("trademark" in warning.lower() for warning in warnings) and recommendation is DomainRecommendation.BUY:
        recommendation = DomainRecommendation.WATCH
    return recommendation


def _meaningful_source_entities(theme: Theme) -> set[str]:
    """Keep only source-specific identifiers that are useful for risk detection."""
    entities: set[str] = set()
    for entity in theme.source_entities:
        normalized = _normalize_candidate_name(entity)
        if len(normalized) < 5:
            continue
        if normalized in GENERIC_SOURCE_ENTITY_TERMS:
            continue
        entities.add(normalized)
    return entities


def _contextual_score_adjustment(
    candidate_name: str,
    candidate_style: str,
    matched_keyword: KeywordInsight,
    theme: Theme,
    profile: str,
) -> tuple[int, tuple[str, ...], bool]:
    """Apply theme-aware exact-match and source-overlap risk handling."""
    notes: list[str] = []
    score_adjustment = 0
    context_rejected = False
    meaningful_entities = _meaningful_source_entities(theme)

    overlapping_entities = [
        entity
        for entity in meaningful_entities
        if candidate_name == entity or candidate_name.startswith(entity) or candidate_name.endswith(entity)
    ]
    if overlapping_entities:
        strongest_entity = max(overlapping_entities, key=len)
        if candidate_name == strongest_entity:
            score_adjustment -= 22
            context_rejected = True
            notes.append("exact overlap with a source-specific project or brand term")
        else:
            score_adjustment -= 12
            notes.append("possible overlap with a source-specific project or brand term")

    if candidate_style in {"exact", "exact_match"}:
        if profile in {"seo_exact", "geo_local"} and matched_keyword.keyword_type in {"commercial_term", "raw_term"}:
            if matched_keyword.commercial_score >= 3.5:
                score_adjustment += 3
                notes.append("exact-match structure fits this buyer profile")
        else:
            score_adjustment -= 4
            notes.append("exact-match structure is weaker for this buyer profile")

    if candidate_style == "premium_compact" and profile in {"startup_brand", "ai_brand", "flip_fast"}:
        if len(candidate_name) <= 8:
            score_adjustment += 2
            notes.append("compact premium-style structure fits the selected profile")

    if any(trademark_term in candidate_name for trademark_term in TRADEMARK_TERMS):
        score_adjustment -= 6
        notes.append("possible trademark overlap heuristic; not legal advice")

    return score_adjustment, tuple(dict.fromkeys(notes)), context_rejected


def _review_bucket_from_opportunity(
    recommendation: DomainRecommendation,
    score: int,
    warnings: tuple[str, ...],
) -> str:
    """Assign the domain to a shortlist, watchlist, or rejected review lane."""
    warning_text = " ".join(warnings).lower()
    high_risk = any(term in warning_text for term in {"trademark", "confusing", "awkward", "hyphen"})

    if recommendation is DomainRecommendation.BUY and score >= 80 and not high_risk:
        return "shortlist"
    if recommendation in {DomainRecommendation.BUY, DomainRecommendation.WATCH} and score >= 65:
        return "watchlist"
    return "rejected"


def _rationale(
    theme: Theme,
    keyword: KeywordInsight,
    explanation: str,
    domain: str,
    context_notes: tuple[str, ...] = (),
) -> str:
    """Build a concise rationale for why the candidate was generated."""
    rationale = (
        f"{explanation} Built from theme '{theme.canonical_name}' using "
        f"{keyword.keyword_type.replace('_', ' ')} '{keyword.keyword}' for {domain}."
    )
    if context_notes:
        rationale += f" Review notes: {'; '.join(context_notes[:2])}."
    return rationale


def generate_domain_opportunities(
    keywords: list[KeywordInsight],
    themes: list[Theme],
) -> list[DomainOpportunity]:
    """Generate and score domain ideas from keyword insights and themes."""
    word_banks = load_word_banks()
    themes_by_name = {theme.canonical_name: theme for theme in themes}
    grouped_keywords = _group_keywords_by_theme(keywords)
    opportunities: list[DomainOpportunity] = []
    seen_domains: set[tuple[str, str, str]] = set()

    for theme_name, theme_keywords in grouped_keywords.items():
        theme = themes_by_name.get(theme_name)
        if theme is None or theme.classification is ItemClassification.IGNORE:
            continue

        seed_keywords = _select_seed_keywords(theme_keywords)
        if not seed_keywords:
            continue

        niche = _pick_niche(theme_keywords)
        buyer_type = _pick_buyer_type(theme_keywords)
        profile = _choose_profile(theme, seed_keywords, niche)
        extensions = _choose_extensions(profile, niche)
        average_commercial_score = (
            sum(keyword.commercial_score for keyword in seed_keywords) / max(len(seed_keywords), 1)
        )
        generated_candidates = _deterministic_generate_candidates(
            theme_name,
            niche,
            [keyword.keyword for keyword in seed_keywords],
            word_banks,
        )
        supplemental_candidates = _build_supplemental_candidates(theme_name, niche, seed_keywords, theme_keywords)

        candidate_pool: dict[str, dict[str, str | bool]] = {}
        for candidate in supplemental_candidates + generated_candidates:
            candidate_name = str(candidate.get("name") or "").strip().lower()
            candidate_style = str(candidate.get("method") or "keyword").strip().lower()
            source_name = str(candidate.get("source_name") or "").strip().lower()
            if not candidate_name or not _is_promising_candidate_name(candidate_name):
                continue
            if candidate_name not in candidate_pool:
                candidate_pool[candidate_name] = {
                    "name": candidate_name,
                    "method": candidate_style,
                    "source_name": source_name,
                    "is_transformed": bool(candidate.get("is_transformed", False)),
                }

        theme_opportunities: list[DomainOpportunity] = []
        for candidate in candidate_pool.values():
            candidate_name = str(candidate.get("name") or "").strip().lower()
            candidate_style = str(candidate.get("method") or "keyword").strip().lower()
            if not candidate_name:
                continue

            matched_keyword = next(
                (
                    keyword
                    for keyword in seed_keywords
                    if keyword.keyword in candidate_name or candidate_name.startswith(keyword.keyword)
                ),
                seed_keywords[0],
            )

            for extension in extensions:
                full_domain = f"{candidate_name}{extension}"
                dedupe_key = (theme_name, candidate_name, extension)
                if dedupe_key in seen_domains:
                    continue
                seen_domains.add(dedupe_key)

                appraisal = evaluate_domain(
                    full_domain,
                    profile=profile,
                    niche=niche,
                    word_banks=word_banks,
                )
                score_adjustment, context_notes, context_rejected = _contextual_score_adjustment(
                    candidate_name,
                    candidate_style,
                    matched_keyword,
                    theme,
                    profile,
                )
                warnings = tuple(dict.fromkeys([*(str(warning) for warning in appraisal.warnings), *context_notes]))
                adjusted_score = max(0, min(100, appraisal.final_score + score_adjustment))
                adjusted_rejected = appraisal.rejected or context_rejected
                adjusted_grade = grade_from_score(adjusted_score, rejected=adjusted_rejected)
                _, adjusted_value = resale_tier_from_grade(adjusted_grade)
                recommendation = _recommendation_from_appraisal(
                    adjusted_score,
                    theme,
                    average_commercial_score,
                    warnings,
                    adjusted_rejected,
                )
                review_bucket = _review_bucket_from_opportunity(
                    recommendation,
                    adjusted_score,
                    warnings,
                )

                rejected_reason = ""
                if review_bucket == "rejected":
                    rejected_reason = "; ".join(warnings[:2]) or appraisal.explanation

                theme_opportunities.append(
                    DomainOpportunity(
                        domain_name=appraisal.name,
                        extension=appraisal.tld,
                        source_theme=theme_name,
                        recommendation=recommendation,
                        keyword=matched_keyword.keyword,
                        niche=niche,
                        buyer_type=buyer_type,
                        style=candidate_style,
                        score=float(adjusted_score),
                        review_bucket=review_bucket,
                        scoring_profile=profile,
                        grade=adjusted_grade,
                        value_estimate=adjusted_value,
                        rationale=_rationale(
                            theme,
                            matched_keyword,
                            appraisal.explanation,
                            full_domain,
                            context_notes=context_notes,
                        ),
                        risk_notes=warnings,
                        rejected_reason=rejected_reason,
                    )
                )

        theme_opportunities.sort(
            key=lambda opportunity: (
                REVIEW_BUCKET_RANK.get(opportunity.review_bucket, -1),
                RECOMMENDATION_RANK[opportunity.recommendation],
                opportunity.score,
                opportunity.grade,
            ),
            reverse=True,
        )
        opportunities.extend(theme_opportunities[:15])

    opportunities.sort(
        key=lambda opportunity: (
            REVIEW_BUCKET_RANK.get(opportunity.review_bucket, -1),
            RECOMMENDATION_RANK[opportunity.recommendation],
            opportunity.score,
            opportunity.source_theme,
        ),
        reverse=True,
    )
    return opportunities
