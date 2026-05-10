"""Pure generation workflow used by the Streamlit generator screen."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence

from generator import NICHE_STATIC_TERMS, generate_domains
from scoring import evaluate_domain, get_profile
from scoring.interfaces import DomainAppraisal
from scoring.scoring import NICHE_HINTS, tokenize_name
from scoring.score_profiles import auto_detect_profile


GRADE_ORDER = ["A+", "A", "B", "C", "D", "Reject"]


GenerateDomainsFn = Callable[..., list[dict[str, Any]]]
EvaluateDomainFn = Callable[..., DomainAppraisal]
TokenizeNameFn = Callable[[str, Optional[Mapping[str, Sequence[str]]], str], list[str]]
AutoDetectProfileFn = Callable[[str, str, Sequence[str], str], str]


@dataclass(frozen=True)
class GenerationWorkflowRequest:
    """Inputs needed to run domain generation without Streamlit state."""

    niches: Sequence[str]
    generation_styles: Sequence[str]
    keywords: str
    geo_context: str
    num_per_tier: int
    extensions: Sequence[str]
    use_llm: bool
    word_banks: Mapping[str, Sequence[str]]
    backend_valuation_map: Mapping[str, Mapping[str, Any]] | None = None
    generated_at: datetime | None = None


@dataclass(frozen=True)
class GenerationDebugSnapshot:
    """Lightweight metadata for the Streamlit debug panel."""

    keyword_list: list[str] = field(default_factory=list)
    geo_context: str = ""
    style_list: list[str] = field(default_factory=list)
    candidate_count: int = 0
    method_counts: dict[str, int] = field(default_factory=dict)
    sample_candidates: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GenerationWorkflowResult:
    """Generated appraisals, history rows, and debug metadata."""

    categories: dict[str, list[dict[str, Any]]]
    history_rows: list[dict[str, Any]]
    debug_snapshot: GenerationDebugSnapshot
    displayed_appraisals: list[dict[str, Any]]


def normalize_keywords_for_workflow(keywords: str) -> list[str]:
    """Mirror Streamlit keyword cleanup for scoring context and debug output."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_keyword in keywords.split(","):
        cleaned = "".join(character for character in raw_keyword.lower().strip() if character.isalpha())
        if len(cleaned) < 3 or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def niche_affinity_score(name: str, tokens: Sequence[str], niche: str) -> int:
    """Score how closely a candidate name belongs to one selected niche."""
    token_set = set(tokens)
    compact_name = "".join(character for character in name.lower() if character.isalpha())
    niche_terms = set(NICHE_STATIC_TERMS.get(niche, ())) | NICHE_HINTS.get(niche, set())
    score = 0
    score += 4 * len(token_set & niche_terms)
    score += sum(2 for term in niche_terms if len(term) >= 4 and term in compact_name)
    return score


def appraisal_to_dict(appraisal: DomainAppraisal) -> dict[str, Any]:
    """Convert a structured appraisal dataclass into a session-friendly dict."""
    return {
        "domain": appraisal.domain,
        "name": appraisal.name,
        "tld": appraisal.tld,
        "profile": appraisal.profile,
        "niche": "",
        "final_score": appraisal.final_score,
        "grade": appraisal.grade,
        "tier": appraisal.tier,
        "value": appraisal.value,
        "subscores": dict(appraisal.subscores),
        "flags": list(appraisal.flags),
        "warnings": list(appraisal.warnings),
        "explanation": appraisal.explanation,
        "rejected": appraisal.rejected,
        "method": "unknown",
        "source_name": "",
        "is_transformed": False,
        "improvement_delta": 0,
        "source_domain": "",
        "backend_valuation": None,
    }


def _unique_ordered(values: Sequence[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _collect_generated_candidates(
    request: GenerationWorkflowRequest,
    generate_domains_fn: GenerateDomainsFn,
) -> list[dict[str, Any]]:
    generated_candidates_map: dict[str, dict[str, Any]] = {}
    for niche in request.niches:
        for candidate in generate_domains_fn(
            niche=niche,
            use_llm=request.use_llm,
            word_banks=request.word_banks,
            requested_styles=request.generation_styles,
            keywords_str=request.keywords,
            geo_context=request.geo_context,
            num_per_tier=request.num_per_tier,
        ):
            candidate_name = str(candidate["name"])
            if candidate_name not in generated_candidates_map:
                generated_candidates_map[candidate_name] = {**candidate, "source_niches": [niche]}
            else:
                generated_candidates_map[candidate_name].setdefault("source_niches", []).append(niche)
    return list(generated_candidates_map.values())


def _best_niche_for_candidate(name: str, tokens: Sequence[str], candidate: Mapping[str, Any], niches: Sequence[str]) -> str:
    candidate_niches = _unique_ordered([*candidate.get("source_niches", []), *niches])
    return max(
        candidate_niches,
        key=lambda item: (
            niche_affinity_score(name, tokens, item),
            -niches.index(item) if item in niches else 0,
        ),
    )


def _apply_backend_valuation_map(
    categories: dict[str, list[dict[str, Any]]],
    backend_valuation_map: Mapping[str, Mapping[str, Any]] | None,
) -> None:
    if not backend_valuation_map:
        return
    normalized_map = {str(domain).lower(): valuation for domain, valuation in backend_valuation_map.items()}
    for appraisals in categories.values():
        for appraisal in appraisals:
            appraisal["backend_valuation"] = normalized_map.get(str(appraisal["domain"]).lower())


def _displayed_appraisals(categories: dict[str, list[dict[str, Any]]], num_per_tier: int) -> list[dict[str, Any]]:
    return [
        appraisal
        for grade in GRADE_ORDER
        for appraisal in categories.get(grade, [])[:num_per_tier]
    ]


def run_generation_workflow(
    request: GenerationWorkflowRequest,
    *,
    generate_domains_fn: GenerateDomainsFn = generate_domains,
    evaluate_domain_fn: EvaluateDomainFn = evaluate_domain,
    tokenize_name_fn: TokenizeNameFn = tokenize_name,
    auto_detect_profile_fn: AutoDetectProfileFn = auto_detect_profile,
) -> GenerationWorkflowResult:
    """Generate, dedupe, score, bucket, and prepare history rows."""
    generated_candidates = _collect_generated_candidates(request, generate_domains_fn)
    user_keywords = normalize_keywords_for_workflow(request.keywords)
    debug_snapshot = GenerationDebugSnapshot(
        keyword_list=user_keywords,
        geo_context=request.geo_context,
        style_list=list(request.generation_styles),
        candidate_count=len(generated_candidates),
        method_counts=dict(Counter(str(candidate.get("method", "unknown")) for candidate in generated_candidates)),
        sample_candidates=[str(candidate["name"]) for candidate in generated_candidates[:12]],
    )

    categories = {grade: [] for grade in GRADE_ORDER}
    history_rows: list[dict[str, Any]] = []
    appraisal_records: list[dict[str, Any]] = []
    appraisal_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    generated_at = request.generated_at or datetime.now()
    generated_at_label = generated_at.strftime("%Y-%m-%d %H:%M")

    for candidate in generated_candidates:
        name = str(candidate["name"])
        tokens = tokenize_name_fn(name, request.word_banks, "startup_brand")
        best_niche = _best_niche_for_candidate(name, tokens, candidate, request.niches)
        for ext in request.extensions:
            full_domain = f"{name}{ext}"
            scoring_profile = auto_detect_profile_fn(name, ext, tokens, best_niche)
            profile_config = get_profile(scoring_profile)
            appraisal = evaluate_domain_fn(
                full_domain,
                profile=scoring_profile,
                niche=best_niche,
                word_banks=request.word_banks,
                user_keywords=user_keywords,
            )
            appraisal_dict = appraisal_to_dict(appraisal)
            appraisal_dict["niche"] = best_niche
            appraisal_dict["method"] = candidate.get("method", "combine")
            appraisal_dict["source_name"] = candidate.get("source_name", "")
            appraisal_dict["is_transformed"] = candidate.get("is_transformed", False)
            appraisal_records.append(appraisal_dict)
            appraisal_lookup[(best_niche, scoring_profile, ext, name)] = appraisal_dict
            history_rows.append(
                {
                    "Domain": full_domain,
                    "Name": name,
                    "Extension": ext,
                    "Grade": appraisal.grade,
                    "Score": appraisal.final_score,
                    "Method": str(candidate.get("method", "combine")).title(),
                    "Profile": f"{profile_config.label} (auto)",
                    "Value": appraisal.value,
                    "Niche": best_niche,
                    "Explanation": appraisal.explanation,
                    "Date": generated_at_label,
                }
            )

    for appraisal_dict in appraisal_records:
        if appraisal_dict["is_transformed"] and appraisal_dict["source_name"]:
            source_key = (
                appraisal_dict["niche"],
                appraisal_dict["profile"],
                appraisal_dict["tld"],
                appraisal_dict["source_name"],
            )
            source_appraisal = appraisal_lookup.get(source_key)
            if source_appraisal:
                appraisal_dict["source_domain"] = source_appraisal["domain"]
                appraisal_dict["improvement_delta"] = appraisal_dict["final_score"] - source_appraisal["final_score"]

        categories[appraisal_dict["grade"]].append(appraisal_dict)

    for grade in categories:
        categories[grade].sort(key=lambda item: item["final_score"], reverse=True)

    _apply_backend_valuation_map(categories, request.backend_valuation_map)
    displayed_appraisals = _displayed_appraisals(categories, request.num_per_tier)
    return GenerationWorkflowResult(
        categories=categories,
        history_rows=history_rows,
        debug_snapshot=debug_snapshot,
        displayed_appraisals=displayed_appraisals,
    )
