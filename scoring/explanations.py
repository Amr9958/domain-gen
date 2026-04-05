"""Human-readable explanation generation for appraisals."""

from __future__ import annotations

from typing import Mapping, Sequence


FLAG_PHRASES = {
    "clean_structure": "clean structure",
    "strong_ai_fit": "strong AI fit",
    "strong_startup_fit": "good startup-brand fit",
    "strong_exact_match_fit": "clear exact-match intent",
    "strong_local_fit": "strong local-service fit",
    "strong_extension_fit": "appropriate extension fit",
    "strong_liquidity": "good resale liquidity",
    "natural_word_order": "natural word order",
    "smooth_pronunciation": "smooth pronunciation",
    "compact_length": "compact length",
}

WARNING_PHRASES = {
    "numbers usually reduce trust and liquidity": "numbers hurt trust and resale appeal",
    "hyphens rarely clear premium resale thresholds": "hyphens weaken premium positioning",
    "join between terms sounds unnatural": "the word join feels awkward",
    "possible trademark overlap heuristic; not legal advice": "there may be trademark overlap risk",
    "extension is weak for local or exact-match buyers": "the extension is weaker for this use case",
    "contains low-trust commercial wording": "the wording feels spammy",
    "awkward ending weakens pronunciation": "the ending is hard to say cleanly",
    "length reduces buyer pool": "the length narrows buyer demand",
    "word order feels unnatural": "the word order feels unnatural",
    "pronunciation is very difficult": "the pronunciation is very difficult",
}


def build_explanation(
    domain: str,
    final_score: int,
    flags: Sequence[str],
    warnings: Sequence[str],
    subscores: Mapping[str, int],
) -> str:
    """Generate a concise appraisal explanation from flags and warnings."""
    _ = domain
    positive_parts = [FLAG_PHRASES[flag] for flag in flags if flag in FLAG_PHRASES][:3]
    warning_parts = [WARNING_PHRASES[warning] for warning in warnings if warning in WARNING_PHRASES][:2]

    if final_score >= 80 and positive_parts:
        sentence = ", ".join(positive_parts[:-1]) + (", and " if len(positive_parts) > 1 else "") + positive_parts[-1]
        return sentence[:1].upper() + sentence[1:] + "."

    if final_score < 65 and warning_parts:
        if len(warning_parts) > 1:
            return f"Scoring is held back because {warning_parts[0]} and {warning_parts[1]}."
        return f"Scoring is held back because {warning_parts[0]}."

    if positive_parts and warning_parts:
        return f"{positive_parts[0].capitalize()}, but {warning_parts[0]}."

    if positive_parts:
        return f"{positive_parts[0].capitalize()} with balanced resale characteristics."

    if warning_parts:
        return f"Scoring is held back because {warning_parts[0]}."

    if subscores.get("brandability", 0) >= 18:
        return "Solid branding potential with acceptable resale characteristics."

    return f"Mixed resale profile with a final score of {final_score}/100."
