"""Domain generation helpers."""

from __future__ import annotations

import random
import re
from typing import Mapping, Sequence

from providers.llm import llm_creative_boost
from scoring.hard_filters import TRADEMARK_TERMS


VOWELS = "aeiou"
INVENT_PREFIXES = (
    "zy", "ter", "vel", "nov", "lum", "syn", "kor", "nex", "sol", "ver", "aer", "zen",
)
INVENT_SUFFIXES = (
    "ta", "ra", "za", "sa", "va", "lo", "ro", "sy", "us", "ix", "a", "o",
)
BRANDABLE_PREFIXES = (
    "al", "av", "cor", "el", "li", "nov", "nex", "or", "sol", "vel", "ver", "zen",
)
BRANDABLE_SUFFIXES = (
    "a", "ara", "era", "exa", "ia", "io", "ira", "iva", "ix", "ora", "ra", "sy",
)
SHORT_ENDINGS = (
    "a", "ex", "ia", "io", "iq", "ix", "ly", "o", "on", "ra", "ro", "ta", "va", "vo",
)
HYBRID_SUFFIXES = (
    "base", "core", "dock", "flow", "forge", "grid", "hub", "labs", "mesh", "mint", "pilot", "stack",
    "vault",
)
AI_SUFFIXES = (
    "agent", "bot", "dock", "flow", "grid", "mesh", "mind", "ops", "pilot", "stack", "vector",
)
AI_MODEL_ENDINGS = (
    "a", "en", "iq", "ix", "on", "ora", "ra", "vo",
)
WEAK_PREFIXES = {
    "best", "cheap", "free", "go", "my", "now", "super", "top", "try", "up", "use",
}
AI_SIGNAL_TERMS = {
    "agent", "ai", "assistant", "automation", "autonomy", "bot", "copilot", "inference", "llm",
    "memory", "model", "neural", "prompt", "reason", "reasoning", "robot", "token", "vector",
    "vision", "voice",
}
GEO_TERMS = {
    "cairo", "dubai", "egypt", "gulf", "ksa", "london", "miami", "riyadh", "saudi", "texas",
    "uae", "uk", "usa",
}
GEO_ALIASES = {
    "egyptian": "egypt",
    "newyork": "newyork",
    "saudiarabia": "saudi",
    "sanfrancisco": "sanfrancisco",
    "unitedarabemirates": "uae",
    "unitedkingdom": "uk",
    "unitedstates": "usa",
}
NICHE_BANKS = {
    "Tech & AI": ("tech", "abstract", "power"),
    "Finance & SaaS": ("finance", "tech", "abstract"),
    "E-commerce": ("creative", "power", "abstract"),
    "Creative & Arts": ("creative", "abstract", "power"),
    "Health & Wellness": ("creative", "abstract"),
    "Real Estate": ("power", "abstract"),
}
NICHE_STATIC_TERMS = {
    "Tech & AI": ("agent", "cloud", "data", "edge", "logic", "model", "node", "prompt", "signal", "vector"),
    "Finance & SaaS": ("audit", "cash", "credit", "fund", "ledger", "pay", "risk", "tax", "trade", "vault"),
    "E-commerce": ("brand", "cart", "catalog", "commerce", "market", "shop", "store", "supply"),
    "Creative & Arts": ("canvas", "craft", "design", "glyph", "muse", "pixel", "render", "studio"),
    "Health & Wellness": ("care", "clinic", "fit", "health", "med", "therapy", "well"),
    "Real Estate": ("estate", "home", "homes", "lease", "property", "realty", "roof"),
}
COMMERCIAL_HEADS_BY_NICHE = {
    "Tech & AI": ("agent", "base", "cloud", "flow", "labs", "mesh", "ops", "pilot", "stack"),
    "Finance & SaaS": ("audit", "capital", "flow", "fund", "ledger", "pay", "risk", "vault"),
    "E-commerce": ("cart", "market", "shop", "stack", "store", "supply"),
    "Creative & Arts": ("canvas", "forge", "labs", "studio", "works"),
    "Health & Wellness": ("care", "clinic", "health", "labs", "well"),
    "Real Estate": ("estate", "home", "homes", "property", "realty", "roof"),
}
ACTION_PREFIXES_BY_NICHE = {
    "Tech & AI": ("build", "launch", "scale", "ship", "sync"),
    "Finance & SaaS": ("compare", "fund", "quote", "secure", "track"),
    "E-commerce": ("build", "launch", "sell", "ship", "stock"),
    "Creative & Arts": ("craft", "design", "render", "shape", "spark"),
    "Health & Wellness": ("book", "find", "heal", "support", "treat"),
    "Real Estate": ("book", "find", "list", "move", "rent"),
}
SPECIAL_ROOTS = (
    ("agent", "agen"),
    ("audio", "aud"),
    ("automation", "auto"),
    ("clinic", "clini"),
    ("credit", "cred"),
    ("data", "data"),
    ("design", "desi"),
    ("finance", "fin"),
    ("health", "heal"),
    ("home", "home"),
    ("legal", "lex"),
    ("payment", "pay"),
    ("payments", "pay"),
    ("property", "prop"),
    ("realestate", "estate"),
    ("security", "secur"),
    ("sound", "son"),
    ("tax", "tax"),
    ("video", "vid"),
    ("vision", "vis"),
    ("voice", "vox"),
)
GENERATION_STYLE_ORDER = (
    "exact",
    "brandable",
    "ai_futuristic",
    "hybrid",
    "short",
    "outbound",
    "geo",
)
AUTO_STYLE = "auto"


def _clean_name(name: str) -> str:
    """Normalize raw text into a compact lower-case candidate."""
    return re.sub(r"[^a-z]", "", name.lower())


def _is_valid_candidate(name: str) -> bool:
    """Keep candidates within a resale-friendly structural window."""
    if not 4 <= len(name) <= 18:
        return False
    if any(trademark_term in name for trademark_term in TRADEMARK_TERMS):
        return False
    if re.search(r"(.)\1\1", name):
        return False
    if len(name) >= 10 and len(set(name)) <= 4:
        return False
    if len(name) >= 8 and len(name) % 2 == 0 and name[: len(name) // 2] == name[len(name) // 2 :]:
        return False
    if any(name.startswith(prefix) and len(name) > len(prefix) + 2 for prefix in WEAK_PREFIXES):
        return False
    return True


def _candidate_record(name: str, method: str, source_name: str = "") -> dict[str, str | bool]:
    """Build a metadata-rich candidate record for downstream comparison."""
    return {
        "name": name,
        "method": method,
        "source_name": source_name,
        "is_transformed": bool(source_name and source_name != name),
    }


def _append_candidate(
    candidates: dict[str, dict[str, str | bool]],
    raw_name: str,
    method: str,
    source_name: str = "",
) -> None:
    """Add a normalized candidate if it clears basic structural checks."""
    clean_name = _clean_name(raw_name)
    clean_source = _clean_name(source_name)
    if not _is_valid_candidate(clean_name):
        return
    if clean_name not in candidates:
        candidates[clean_name] = _candidate_record(clean_name, method, clean_source)


def _ordered_unique(words: Sequence[str]) -> list[str]:
    """Preserve input order while removing empty or duplicate values."""
    ordered: list[str] = []
    seen: set[str] = set()
    for word in words:
        if not word or word in seen:
            continue
        seen.add(word)
        ordered.append(word)
    return ordered


def _deterministic_take(words: Sequence[str], limit: int) -> list[str]:
    """Pick a stable shuffled slice based on the current seeded RNG state."""
    pool = _ordered_unique([_clean_name(word) for word in words if _clean_name(word)])
    random.shuffle(pool)
    return pool[:limit]


def _random_bank_word(word_banks: Mapping[str, Sequence[str]], excluded: set[str]) -> str:
    """Pick a random word from any non-excluded bank."""
    categories = [category for category in word_banks.keys() if category not in excluded and word_banks[category]]
    category = random.choice(categories)
    return random.choice(word_banks[category])


def _normalize_keywords(keywords_str: str) -> list[str]:
    """Parse and deduplicate user-selected keywords."""
    ordered_keywords: list[str] = []
    seen: set[str] = set()
    for raw_keyword in keywords_str.split(","):
        clean_keyword = _clean_name(raw_keyword.strip())
        if len(clean_keyword) < 3 or clean_keyword in seen:
            continue
        seen.add(clean_keyword)
        ordered_keywords.append(clean_keyword)
    return ordered_keywords


def _normalize_requested_styles(requested_styles: Sequence[str] | None) -> list[str]:
    """Normalize user-requested generation styles while keeping Auto mutually exclusive."""
    if not requested_styles:
        return [AUTO_STYLE]

    cleaned_styles: list[str] = []
    seen: set[str] = set()
    for style in requested_styles:
        normalized_style = str(style or "").strip().lower()
        if not normalized_style or normalized_style in seen:
            continue
        seen.add(normalized_style)
        cleaned_styles.append(normalized_style)

    if not cleaned_styles:
        return [AUTO_STYLE]
    if AUTO_STYLE in cleaned_styles and len(cleaned_styles) > 1:
        cleaned_styles = [style for style in cleaned_styles if style != AUTO_STYLE]
    return cleaned_styles or [AUTO_STYLE]


def _normalize_geo_terms(geo_context: str | Sequence[str] | None) -> list[str]:
    """Normalize explicit geo input into compact reusable location tokens."""
    if not geo_context:
        return []

    if isinstance(geo_context, str):
        raw_values = geo_context.split(",")
    else:
        raw_values = [str(value) for value in geo_context]

    normalized_values: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        clean_value = _clean_name(raw_value.strip())
        if len(clean_value) < 3:
            continue
        canonical_value = GEO_ALIASES.get(clean_value, clean_value)
        if canonical_value in seen:
            continue
        seen.add(canonical_value)
        normalized_values.append(canonical_value)
    return normalized_values


def _auto_generation_styles(niche: str, user_keywords: Sequence[str], geo_terms: Sequence[str]) -> list[str]:
    """Pick styles automatically from the niche plus selected keywords."""
    keyword_set = {keyword for keyword in user_keywords if keyword}
    signal_terms = keyword_set | set(niche.strip().lower().replace("&", " ").replace("/", " ").split())

    styles: list[str] = []
    if niche == "Tech & AI" or signal_terms & AI_SIGNAL_TERMS:
        styles.extend(["ai_futuristic", "hybrid", "brandable", "short", "outbound", "exact"])
    elif niche == "Finance & SaaS":
        styles.extend(["hybrid", "brandable", "exact", "short", "outbound"])
    elif niche in {"Health & Wellness", "Real Estate"}:
        styles.extend(["exact", "hybrid", "outbound", "brandable", "short"])
    else:
        styles.extend(["brandable", "hybrid", "exact", "short", "outbound"])

    if geo_terms or keyword_set & GEO_TERMS:
        styles.append("geo")

    return _ordered_unique(styles)


def _resolve_generation_styles(
    niche: str,
    user_keywords: Sequence[str],
    geo_terms: Sequence[str],
    requested_styles: Sequence[str] | None,
) -> list[str]:
    """Resolve either user-selected or automatic generation styles."""
    normalized_styles = _normalize_requested_styles(requested_styles)
    if normalized_styles == [AUTO_STYLE]:
        return _auto_generation_styles(niche, user_keywords, geo_terms)
    return [style for style in GENERATION_STYLE_ORDER if style in normalized_styles]


def _merge_parts(left: str, right: str) -> str:
    """Join two strings while trimming obvious overlap at the boundary."""
    if not left:
        return right
    if not right:
        return left
    if left[-1] == right[0]:
        return left + right[1:]
    return left + right


def _keyword_front(word: str) -> str:
    """Take a reusable front chunk from a selected keyword."""
    if len(word) <= 5:
        return word
    return word[: max(3, min(6, (len(word) + 1) // 2))]


def _keyword_back(word: str) -> str:
    """Take a reusable back chunk from a selected keyword."""
    if len(word) <= 5:
        return word
    return word[-max(3, min(6, len(word) // 2)) :]


def _brand_root(word: str) -> str:
    """Create a compact root that still preserves the source word feel."""
    clean_word = _clean_name(word)
    for source, replacement in SPECIAL_ROOTS:
        if clean_word.startswith(source):
            return replacement

    root = _keyword_front(clean_word)
    for suffix in ("ation", "ition", "ment", "ness", "ings", "tion", "ers", "ing", "ics", "ion"):
        if root.endswith(suffix) and len(root) - len(suffix) >= 3:
            root = root[: -len(suffix)]
            break

    if len(root) > 5:
        root = root[:4]
    if len(root) >= 4 and root[-1] not in VOWELS:
        root = root[:-1]
    return root or clean_word[:3]


def _build_keyword_base_names(user_keywords: Sequence[str], target_count: int) -> list[tuple[str, str]]:
    """Generate keyword-anchored base names using only selected keywords and their fragments."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(raw_name: str, method: str) -> None:
        clean_name = _clean_name(raw_name)
        if not _is_valid_candidate(clean_name) or clean_name in seen:
            return
        seen.add(clean_name)
        results.append((clean_name, method))

    for keyword in user_keywords:
        add(keyword, "keyword")
        add(_cut_name(keyword), "cut")
        add(_twist_name(keyword), "twist")
        if len(results) >= target_count:
            return results

    for left in user_keywords:
        for right in user_keywords:
            if left == right:
                continue
            add(_merge_parts(left, right), "combine")
            add(_merge_parts(_keyword_front(left), right), "combine")
            add(_merge_parts(left, _keyword_back(right)), "combine")
            add(_merge_parts(_keyword_front(left), _keyword_back(right)), "blend")
            if len(results) >= target_count:
                return results

    return results


def _build_base_name(
    word_banks: Mapping[str, Sequence[str]],
    user_keywords: Sequence[str],
) -> tuple[str, str]:
    """Generate a seed candidate using combine-oriented rules."""
    word1 = _random_bank_word(word_banks, {"short_prefixes"})
    roll = random.random()

    if user_keywords and roll > 0.35:
        keyword = random.choice(user_keywords)
        if random.random() > 0.5:
            return keyword + word1, "combine"
        return word1 + keyword, "combine"

    if roll > 0.7 and word_banks.get("short_prefixes"):
        prefix = random.choice(word_banks["short_prefixes"])
        return prefix + word1, "combine"

    word2 = _random_bank_word(word_banks, {"short_prefixes"})
    return word1 + word2, "combine"


def _twist_name(name: str) -> str:
    """Create a phonetic brand twist from a base name."""
    if len(name) < 4:
        return ""
    if name.endswith("e") and len(name) >= 5:
        return name[:-1] + "a"
    if name.endswith(("er", "or")) and len(name) >= 6:
        return name[:-2] + "ra"
    if name[-1] not in VOWELS and len(name) <= 9:
        return name + random.choice(("a", "o", "i"))
    return name[:-1] + random.choice(("a", "o")) if len(name) >= 5 else ""


def _cut_name(name: str) -> str:
    """Shorten a name while trying to preserve readability."""
    if len(name) <= 5:
        return ""
    if name.endswith(("al", "el", "er", "or", "um")):
        return name[:-1]
    if name.endswith("ex") and len(name) >= 6:
        return name[:-1]
    if len(name) >= 7:
        return name[:-1]
    return ""


def _invent_name() -> str:
    """Build an invented but pronounceable brand-style candidate."""
    prefix = random.choice(INVENT_PREFIXES)
    suffix = random.choice(INVENT_SUFFIXES)
    middle = random.choice(("", "", random.choice(("n", "r", "s", "l"))))
    return prefix + middle + suffix


def _build_mode_candidates(
    terms: Sequence[str],
    limit: int,
    builder,
) -> list[dict[str, str | bool]]:
    """Run a builder with local deduplication and a candidate cap."""
    results: list[dict[str, str | bool]] = []
    seen: set[str] = set()

    def add(raw_name: str, method: str, source_name: str = "") -> None:
        clean_name = _clean_name(raw_name)
        clean_source = _clean_name(source_name)
        if len(results) >= limit or not _is_valid_candidate(clean_name) or clean_name in seen:
            return
        seen.add(clean_name)
        results.append(_candidate_record(clean_name, method, clean_source))

    builder(add, terms)
    return results


def _support_terms_for_niche(niche: str, word_banks: Mapping[str, Sequence[str]]) -> list[str]:
    """Derive deterministic support vocabulary from the selected niche and local word banks."""
    bank_categories = NICHE_BANKS.get(niche, ("abstract", "power"))
    bank_words: list[str] = []
    for category in bank_categories:
        bank_words.extend(word_banks.get(category, []))
    safe_prefixes = [word for word in word_banks.get("short_prefixes", []) if word not in WEAK_PREFIXES]
    support_terms = _ordered_unique(
        [
            *_deterministic_take(NICHE_STATIC_TERMS.get(niche, ()), 10),
            *_deterministic_take(bank_words, 8),
            *_deterministic_take(safe_prefixes, 4),
        ]
    )
    return support_terms[:16]


def _build_exact_candidates(
    terms: Sequence[str],
    niche: str,
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate exact-match and descriptive keyword candidates."""
    heads = _ordered_unique([*COMMERCIAL_HEADS_BY_NICHE.get(niche, ()), *support_terms])

    def builder(add, input_terms: Sequence[str]) -> None:
        for keyword in input_terms[:5]:
            add(keyword, "keyword")
            for head in heads[:6]:
                if head == keyword or head in keyword or keyword in head:
                    continue
                add(_merge_parts(keyword, head), "exact", source_name=keyword)
                if len(keyword) <= 7:
                    add(_merge_parts(_keyword_front(keyword), head), "descriptive", source_name=keyword)

        for left in input_terms[:3]:
            for right in heads[:5]:
                if left == right or right in left:
                    continue
                add(_merge_parts(left, right), "exact_match", source_name=left)

    return _build_mode_candidates(terms, limit, builder)


def _build_hybrid_candidates(
    terms: Sequence[str],
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate brand-forward hybrid names with commercial anchors."""
    suffixes = _ordered_unique([*HYBRID_SUFFIXES, *support_terms])
    prefixes = _deterministic_take([*BRANDABLE_PREFIXES, *support_terms], 8)

    def builder(add, input_terms: Sequence[str]) -> None:
        for keyword in input_terms[:5]:
            root = _brand_root(keyword)
            for suffix in suffixes[:5]:
                if suffix in keyword:
                    continue
                add(_merge_parts(keyword, suffix), "hybrid", source_name=keyword)
                add(_merge_parts(root, suffix), "hybrid", source_name=keyword)
            for prefix in prefixes[:3]:
                if prefix == keyword:
                    continue
                add(_merge_parts(prefix, keyword), "hybrid", source_name=keyword)

    return _build_mode_candidates(terms, limit, builder)


def _build_brandable_candidates(
    terms: Sequence[str],
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate startup-style brandable candidates without requiring the LLM."""
    endings = _deterministic_take(BRANDABLE_SUFFIXES, 6)
    prefixes = _deterministic_take(BRANDABLE_PREFIXES, 6)

    def builder(add, input_terms: Sequence[str]) -> None:
        for keyword in input_terms[:5]:
            root = _brand_root(keyword)
            back = _keyword_back(keyword)[-3:]
            for ending in endings[:4]:
                add(_merge_parts(root, ending), "brandable", source_name=keyword)
            for prefix in prefixes[:3]:
                add(_merge_parts(prefix, back), "brandable", source_name=keyword)
            for partner in support_terms[:3]:
                partner_root = _brand_root(partner)
                if partner_root == root:
                    continue
                add(_merge_parts(root, partner_root[-2:]), "brandable", source_name=keyword)

        if not input_terms:
            for _ in range(limit):
                add(_invent_name(), "invent")

    return _build_mode_candidates(terms, limit, builder)


def _build_short_candidates(
    terms: Sequence[str],
    word_banks: Mapping[str, Sequence[str]],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate compact short names from keyword roots and safe short prefixes."""
    safe_prefixes = [word for word in word_banks.get("short_prefixes", []) if word not in WEAK_PREFIXES]
    endings = _deterministic_take(SHORT_ENDINGS, 6)

    def builder(add, input_terms: Sequence[str]) -> None:
        roots = _ordered_unique(
            [*_deterministic_take([_brand_root(term)[:3] for term in input_terms], 6), *_deterministic_take(safe_prefixes, 6)]
        )
        for root in roots:
            trimmed_root = root[:3]
            for ending in endings[:3]:
                candidate = _merge_parts(trimmed_root, ending)
                if 4 <= len(candidate) <= 6:
                    add(candidate, "short", source_name=root)
        for keyword in input_terms[:3]:
            cut_name = _cut_name(keyword)
            if 4 <= len(cut_name) <= 6:
                add(cut_name, "short", source_name=keyword)

    return _build_mode_candidates(terms, limit, builder)


def _build_ai_candidates(
    terms: Sequence[str],
    niche: str,
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate AI-native or futuristic candidates when the niche signals support it."""
    signal_terms = set(terms)
    if niche != "Tech & AI" and not (signal_terms & AI_SIGNAL_TERMS):
        return []

    suffixes = _deterministic_take(AI_SUFFIXES, 7)
    model_endings = _deterministic_take(AI_MODEL_ENDINGS, 5)

    def builder(add, input_terms: Sequence[str]) -> None:
        for keyword in input_terms[:5]:
            root = _brand_root(keyword)
            for suffix in suffixes[:4]:
                if suffix in keyword:
                    continue
                add(_merge_parts(root, suffix), "ai", source_name=keyword)
            for ending in model_endings[:3]:
                add(_merge_parts(root, ending), "ai_model", source_name=keyword)

    return _build_mode_candidates(terms, limit, builder)


def _build_action_candidates(
    terms: Sequence[str],
    niche: str,
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate outbound-friendly action-oriented candidates."""
    action_prefixes = ACTION_PREFIXES_BY_NICHE.get(niche, ACTION_PREFIXES_BY_NICHE["Tech & AI"])

    def builder(add, input_terms: Sequence[str]) -> None:
        for keyword in input_terms[:4]:
            for action in action_prefixes[:3]:
                add(_merge_parts(action, keyword), "action", source_name=keyword)

    return _build_mode_candidates(terms, limit, builder)


def _build_geo_candidates(
    geo_terms: Sequence[str],
    user_keywords: Sequence[str],
    niche: str,
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate geo-targeted candidates only when explicit geo terms are provided."""
    inferred_geo_terms = [keyword for keyword in user_keywords if keyword in GEO_TERMS]
    selected_geo_terms = _ordered_unique([*geo_terms, *inferred_geo_terms])
    service_terms = [
        keyword
        for keyword in user_keywords
        if keyword not in selected_geo_terms and keyword not in GEO_TERMS
    ]
    if not selected_geo_terms:
        return []

    base_services = _ordered_unique([*service_terms, *COMMERCIAL_HEADS_BY_NICHE.get(niche, ()), *support_terms])

    def builder(add, input_terms: Sequence[str]) -> None:
        _ = input_terms
        for geo in selected_geo_terms[:3]:
            for service in base_services[:4]:
                if service == geo:
                    continue
                add(_merge_parts(geo, service), "geo", source_name=geo)
            for suffix in ("flow", "group", "labs", "works"):
                add(_merge_parts(geo, suffix), "geo_brandable", source_name=geo)

    return _build_mode_candidates(selected_geo_terms, limit, builder)


def _build_legacy_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    word_banks: Mapping[str, Sequence[str]],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Backfill with the older combine/twist/cut/invent patterns for diversity."""
    seed_terms = list(user_keywords[:4]) or list(support_terms[:4])
    results: dict[str, dict[str, str | bool]] = {}

    if seed_terms:
        for clean_name, method in _build_keyword_base_names(seed_terms, limit):
            _append_candidate(results, clean_name, method)

    attempts = max(limit * 3, 12)
    while len(results) < limit and attempts > 0:
        attempts -= 1
        raw_name, method = _build_base_name(word_banks, seed_terms)
        _append_candidate(results, raw_name, method)
        _append_candidate(results, _twist_name(_clean_name(raw_name)), "twist", source_name=_clean_name(raw_name))
        _append_candidate(results, _cut_name(_clean_name(raw_name)), "cut", source_name=_clean_name(raw_name))

    while len(results) < limit:
        _append_candidate(results, _invent_name(), "invent")

    return list(results.values())[:limit]


def generate_domains(
    niche: str,
    use_llm: bool,
    word_banks: Mapping[str, Sequence[str]],
    requested_styles: Sequence[str] | None = None,
    keywords_str: str = "",
    geo_context: str = "",
    num_per_tier: int = 15,
) -> list[dict[str, str | bool]]:
    """Generate a diversified candidate pool with an improved offline fallback engine."""
    user_keywords = _normalize_keywords(keywords_str)
    geo_terms = _normalize_geo_terms(geo_context)
    random_state = random.getstate()
    random.seed(f"{niche}|{','.join(user_keywords)}|{','.join(geo_terms)}|{num_per_tier}")
    try:
        support_terms = _support_terms_for_niche(niche, word_banks)
        working_terms = _ordered_unique([*user_keywords, *support_terms])
        candidates: dict[str, dict[str, str | bool]] = {}
        per_mode_limit = max(4, min(num_per_tier, 8))
        resolved_styles = _resolve_generation_styles(niche, user_keywords, geo_terms, requested_styles)

        candidate_sets: list[list[dict[str, str | bool]]] = []
        if "exact" in resolved_styles:
            candidate_sets.append(_build_exact_candidates(working_terms, niche, support_terms, per_mode_limit + 2))
        if "hybrid" in resolved_styles:
            candidate_sets.append(_build_hybrid_candidates(working_terms, support_terms, per_mode_limit + 2))
        if "brandable" in resolved_styles:
            candidate_sets.append(_build_brandable_candidates(working_terms, support_terms, per_mode_limit + 1))
        if "ai_futuristic" in resolved_styles:
            candidate_sets.append(_build_ai_candidates(working_terms, niche, per_mode_limit))
        if "short" in resolved_styles:
            candidate_sets.append(_build_short_candidates(working_terms, word_banks, max(4, per_mode_limit - 1)))
        if "outbound" in resolved_styles:
            candidate_sets.append(_build_action_candidates(working_terms, niche, max(4, per_mode_limit - 1)))
        if "geo" in resolved_styles:
            candidate_sets.append(
                _build_geo_candidates(geo_terms, user_keywords, niche, support_terms, max(4, per_mode_limit - 2))
            )

        if _normalize_requested_styles(requested_styles) == [AUTO_STYLE]:
            candidate_sets.append(_build_legacy_candidates(user_keywords, support_terms, word_banks, max(5, per_mode_limit)))

        for candidate_group in candidate_sets:
            for candidate in candidate_group:
                _append_candidate(
                    candidates,
                    str(candidate.get("name") or ""),
                    str(candidate.get("method") or "combine"),
                    source_name=str(candidate.get("source_name") or ""),
                )

        if use_llm:
            llm_suggestions = llm_creative_boost(
                niche,
                list(candidates.keys()),
                selected_keywords=user_keywords,
                requested_styles=resolved_styles,
                geo_context=geo_context,
                count=max(num_per_tier, len(user_keywords), 8),
            )
            for suggestion in llm_suggestions:
                _append_candidate(
                    candidates,
                    str(suggestion.get("name") or ""),
                    str(suggestion.get("method") or "llm"),
                )

        return list(candidates.values())
    finally:
        random.setstate(random_state)
