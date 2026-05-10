"""Domain generation helpers."""

from __future__ import annotations

import random
import re
from collections import Counter
from typing import Mapping, Sequence

from constants import AUTO_STYLE, GENERATION_STYLE_ORDER
from scoring.hard_filters import TRADEMARK_TERMS


VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"
SYLLABLE_ONSETS = ("b", "c", "d", "f", "l", "m", "n", "r", "s", "t", "v", "z")
SYLLABLE_NUCLEI = ("a", "e", "i", "o", "u")
SYLLABLE_CODAS = ("", "", "l", "n", "r", "s", "x")
# مجموعات أصوات متنوعة لتوليد أسماء مخترعة وقابلة للنطق
INVENT_PREFIXES = (
    "aer", "bri", "cal", "dex", "flo", "kor", "lum", "mav", "nex", "nov",
    "ori", "pal", "qua", "ren", "sol", "syn", "ter", "vel", "xen", "zen", "zy",
)
INVENT_SUFFIXES = (
    "a", "an", "ara", "ix", "lo", "o", "on", "ra", "ro", "sa",
    "sy", "ta", "us", "va", "za",
)
# بادئات ونهايات لتوليد أسماء Brandable
BRANDABLE_PREFIXES = (
    "al", "am", "av", "co", "cor", "el", "en", "ev", "in", "li", "lu",
    "nav", "nex", "nov", "or", "qu", "ri", "sol", "su", "vel", "ver", "vi", "zen",
)
BRANDABLE_SUFFIXES = (
    "a", "ai", "ana", "ara", "ea", "era", "exa", "ia", "ify", "io",
    "ira", "ity", "iva", "ix", "ly", "o", "on", "ora", "ra", "sy", "ux",
)
SHORT_ENDINGS = (
    "a", "ai", "en", "ex", "ia", "id", "io", "iq", "it", "ix", "ly",
    "o", "on", "os", "ra", "ro", "ta", "up", "us", "va", "vo",
)
# لواحق تجارية للأسماء المركبة (Compound)
HYBRID_SUFFIXES = (
    "base", "bit", "box", "core", "craft", "deck", "dock", "drop", "edge",
    "flow", "forge", "gate", "grid", "hive", "hub", "labs", "link", "mark",
    "mesh", "mind", "mint", "nest", "node", "ops", "pad", "path",
    "pilot", "pod", "point", "port", "pulse", "rise", "shift", "space",
    "spark", "spot", "stack", "sync", "vault", "verse", "wave", "wire", "works", "zone",
)
WEAK_PREFIXES = {
    "best", "cheap", "free", "go", "my", "now", "super", "top", "try", "up", "use",
}
ACRONYM_KEYWORDS = {
    "api", "crm", "dns", "erp", "llm", "mcp", "pos", "sdk", "seo", "sms", "vpn",
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
GENERATION_STYLE_ALIASES = {
    "hybrid": "compound",
    "ai_futuristic": "invented",
    "outbound": "exact",
}
NICHE_BANKS = {
    "Tech & SaaS": ("tech", "common_modifiers", "brandable_fragments", "premium_words"),
    "Finance & Fintech": ("finance", "tech", "common_modifiers", "premium_words"),
    "E-commerce & Retail": ("commerce", "common_modifiers", "brandable_fragments", "premium_words"),
    "Travel & Lifestyle": ("travel", "common_modifiers", "brandable_fragments", "premium_words"),
    "Health & Medical": ("health", "common_modifiers", "brandable_fragments", "premium_words"),
    "Real Estate & Property": ("property", "common_modifiers", "power", "premium_words"),
    "Education & Learning": ("education", "common_modifiers", "brandable_fragments", "premium_words"),
    "Legal & Professional": ("legal", "common_modifiers", "brandable_fragments", "premium_words"),
    "Crypto & Web3": ("crypto", "finance", "tech", "premium_words"),
}
NICHE_STATIC_TERMS = {
    "Tech & SaaS": (
        "agent", "api", "cloud", "data", "deploy", "edge", "infra", "logic", "model", "node",
        "pipeline", "prompt", "runtime", "saas", "signal", "vector",
    ),
    "Finance & Fintech": ("audit", "cash", "credit", "fund", "ledger", "pay", "risk", "tax", "trade", "vault"),
    "E-commerce & Retail": (
        "brand", "cart", "catalog", "checkout", "commerce", "dropship", "fulfil", "listing",
        "market", "retail", "shop", "store", "supply", "vendor",
    ),
    "Travel & Lifestyle": (
        "booking", "discover", "escape", "getaway", "guide", "journey", "lifestyle", "retreat",
        "roam", "stay", "tour", "travel", "trip", "wander",
    ),
    "Health & Medical": ("care", "clinic", "fit", "health", "med", "patient", "therapy", "well"),
    "Real Estate & Property": ("estate", "home", "homes", "lease", "property", "realty", "roof"),
    "Education & Learning": ("academy", "class", "course", "learn", "lesson", "school", "skill", "study", "tutor"),
    "Legal & Professional": ("advisor", "case", "compliance", "contract", "counsel", "legal", "pro", "tax"),
    "Crypto & Web3": (
        "bridge", "chain", "crypto", "dao", "defi", "governance", "ledger", "liquidity",
        "oracle", "protocol", "token", "wallet", "web3", "yield",
    ),
}
COMMERCIAL_HEADS_BY_NICHE = {
    "Tech & SaaS": ("agent", "base", "cloud", "flow", "labs", "mesh", "ops", "pilot", "stack"),
    "Finance & Fintech": ("audit", "capital", "flow", "fund", "ledger", "pay", "risk", "vault"),
    "E-commerce & Retail": ("cart", "market", "retail", "shop", "store", "supply"),
    "Travel & Lifestyle": ("booking", "escape", "guide", "stay", "tour", "travel", "trip"),
    "Health & Medical": ("care", "clinic", "health", "labs", "med", "well"),
    "Real Estate & Property": ("estate", "home", "homes", "property", "realty", "roof"),
    "Education & Learning": ("academy", "class", "course", "learn", "school", "skill", "tutor"),
    "Legal & Professional": ("case", "compliance", "contract", "counsel", "legal", "tax"),
    "Crypto & Web3": ("chain", "dao", "defi", "ledger", "token", "vault", "wallet"),
}
SPECIAL_ROOTS = (
    ("academy", "acad"),
    ("agent", "agen"),
    ("audio", "aud"),
    ("automation", "auto"),
    ("clinic", "clini"),
    ("credit", "cred"),
    ("crypto", "cryp"),
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
    ("solution", "sol"),
    ("solutions", "sol"),
    ("sound", "son"),
    ("tax", "tax"),
    ("travel", "trav"),
    ("video", "vid"),
    ("vision", "vis"),
    ("voice", "vox"),
)
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


def _vowel_ratio(name: str) -> float:
    """Return the vowel share used by fast candidate quality gates."""
    return sum(char in VOWELS for char in name) / max(len(name), 1)


def _keyword_acronym_anchors(user_keywords: Sequence[str]) -> tuple[str, ...]:
    """Return short keyword acronyms that should be treated as readable anchors."""
    anchors: list[str] = []
    for keyword in user_keywords:
        clean_keyword = _clean_name(keyword)
        if not 3 <= len(clean_keyword) <= 4:
            continue
        if clean_keyword in ACRONYM_KEYWORDS or _vowel_ratio(clean_keyword) <= 0.34:
            anchors.append(clean_keyword)
    return tuple(_ordered_unique(anchors))


def _primary_keyword_anchor(user_keywords: Sequence[str]) -> str:
    """Return the first acronym-like keyword that must remain visible in generated names."""
    anchors = _keyword_acronym_anchors(user_keywords[:1])
    return anchors[0] if anchors else ""


def _quality_scan_name(name: str, acronym_anchors: Sequence[str]) -> str:
    """Scan acronym-led names by the readable part after the acronym boundary."""
    for anchor in sorted(acronym_anchors, key=len, reverse=True):
        if name.startswith(anchor) and len(name) > len(anchor):
            return name[len(anchor):]
        if name.endswith(anchor) and len(name) > len(anchor):
            return name[: -len(anchor)]
    return name


def _early_reject(name: str, acronym_anchors: Sequence[str] = ()) -> bool:
    """Drop weak names before they enter full scoring."""
    if len(name) > 15:
        return True
    scan_name = _quality_scan_name(name, acronym_anchors)
    if re.search(r"[^aeiou]{4,}", scan_name):
        return True
    if _vowel_ratio(scan_name) < 0.20:
        return True
    return False


def _is_pronounceable(
    name: str,
    min_vowel_ratio: float = 0.30,
    max_vowel_ratio: float = 0.60,
    acronym_anchors: Sequence[str] = (),
) -> bool:
    """Reject generated names with weak vowel balance or harsh consonant clusters."""
    clean_name = _clean_name(name)
    if not clean_name:
        return False
    scan_name = _quality_scan_name(clean_name, acronym_anchors)
    vowel_count = sum(1 for character in clean_name if character in VOWELS)
    vowel_ratio = vowel_count / len(clean_name)
    if not min_vowel_ratio <= vowel_ratio <= max_vowel_ratio:
        return False
    if re.search(r"[^aeiou]{4,}", scan_name):
        return False
    if re.search(r"[aeiou]{4,}", scan_name):
        return False
    return True


def _cvcv_name() -> str:
    """Generate a compact CVCV short-name pattern."""
    return "".join(
        [
            random.choice(CONSONANTS),
            random.choice(VOWELS),
            random.choice(CONSONANTS),
            random.choice(VOWELS),
        ]
    )


def _candidate_record(name: str, method: str, source_name: str = "") -> dict[str, str | bool]:
    """Build a metadata-rich candidate record for downstream comparison."""
    return {
        "name": name,
        "method": method,
        "source_name": source_name,
        "is_transformed": bool(source_name and source_name != name),
    }


def _candidate_quality_score(candidate: Mapping[str, str | bool]) -> tuple[int, int, int, int]:
    """Rank candidates for diversity trimming before full scoring runs."""
    name = str(candidate.get("name") or "")
    method = str(candidate.get("method") or "")
    length = len(name)
    length_score = 12 - abs(length - 8)
    method_score = {
        "keyword": 6,
        "exact": 6,
        "exact_match": 5,
        "exact_cross": 5,
        "compound": 4,
        "compound_reverse": 2,
        "brandable": 5,
        "brandable_twist": 4,
        "invented": 4,
        "short": 4,
        "geo": 7,
        "geo_brandable": 3,
    }.get(method, 1)
    ending_score = 2 if name.endswith(tuple(VOWELS)) else 0
    cluster_penalty = -2 if re.search(r"[^aeiou]{4,}", name) else 0
    return (method_score, length_score, ending_score + cluster_penalty, -length)


def _style_bucket(method: str) -> str:
    """Map detailed generation methods back to the public style family."""
    if method.startswith("geo"):
        return "geo"
    if method.startswith("exact") or method in {"keyword", "descriptive"}:
        return "exact"
    if method.startswith("compound"):
        return "compound"
    if method.startswith("brandable"):
        return "brandable"
    if method.startswith("invent"):
        return "invented"
    if method.startswith("short"):
        return "short"
    return method or "unknown"


def _diversity_filter(
    candidates: Sequence[Mapping[str, str | bool]],
    user_keywords: Sequence[str] = (),
    max_per_root: int = 3,
) -> list[dict[str, str | bool]]:
    """Limit repeated four-letter roots while preserving survivor order."""
    user_roots = {kw[:4] for kw in user_keywords if len(kw) >= 4}
    grouped: dict[str, list[Mapping[str, str | bool]]] = {}
    for candidate in candidates:
        name = str(candidate.get("name") or "")
        grouped.setdefault(name[:4], []).append(candidate)

    allowed_by_root: dict[str, set[str]] = {}
    for root, group in grouped.items():
        limit = max_per_root + 3 if root in user_roots else max_per_root
        ranked = sorted(group, key=_candidate_quality_score, reverse=True)
        selected: list[Mapping[str, str | bool]] = []
        for style in ("geo", "exact", "compound", "brandable", "invented", "short"):
            if len(selected) >= limit:
                break
            style_candidates = [
                candidate
                for candidate in ranked
                if _style_bucket(str(candidate.get("method") or "")) == style
                and str(candidate.get("name") or "") not in {str(item.get("name") or "") for item in selected}
            ]
            if style_candidates:
                selected.append(style_candidates[0])
        for candidate in ranked:
            if len(selected) >= limit:
                break
            if str(candidate.get("name") or "") in {str(item.get("name") or "") for item in selected}:
                continue
            selected.append(candidate)
        allowed_by_root[root] = {str(candidate.get("name") or "") for candidate in selected}

    filtered: list[dict[str, str | bool]] = []
    seen: set[str] = set()
    for candidate in candidates:
        name = str(candidate.get("name") or "")
        if name in seen or name not in allowed_by_root.get(name[:4], set()):
            continue
        seen.add(name)
        filtered.append(dict(candidate))
    return filtered


def _style_balance_filter(
    candidates: Sequence[Mapping[str, str | bool]],
    max_share: float = 0.40,
    target_share: float = 0.30,
) -> list[dict[str, str | bool]]:
    """Trim overrepresented style families after candidate generation."""
    if not candidates:
        return []

    total = len(candidates)
    style_counts = Counter(_style_bucket(str(candidate.get("method") or "")) for candidate in candidates)
    caps = {
        style: max(1, int(total * target_share))
        for style, count in style_counts.items()
        if count / total > max_share
    }
    if not caps:
        return [dict(candidate) for candidate in candidates]

    allowed_by_style: dict[str, set[str]] = {}
    for style, cap in caps.items():
        group = [candidate for candidate in candidates if _style_bucket(str(candidate.get("method") or "")) == style]
        ranked = sorted(group, key=_candidate_quality_score, reverse=True)
        allowed_by_style[style] = {str(candidate.get("name") or "") for candidate in ranked[:cap]}

    filtered: list[dict[str, str | bool]] = []
    for candidate in candidates:
        method = str(candidate.get("method") or "")
        style = _style_bucket(method)
        name = str(candidate.get("name") or "")
        if style in allowed_by_style and name not in allowed_by_style[style]:
            continue
        filtered.append(dict(candidate))
    return filtered


def _visible_keyword_filter(
    candidates: Sequence[Mapping[str, str | bool]],
    primary_keyword: str,
) -> list[dict[str, str | bool]]:
    """Keep acronym-primary keyword runs visibly anchored to the selected keyword."""
    if not primary_keyword:
        return [dict(candidate) for candidate in candidates]
    anchored = [
        dict(candidate)
        for candidate in candidates
        if primary_keyword in str(candidate.get("name") or "")
    ]
    return anchored or [dict(candidate) for candidate in candidates]


def _append_candidate(
    candidates: dict[str, dict[str, str | bool]],
    raw_name: str,
    method: str,
    source_name: str = "",
    acronym_anchors: Sequence[str] = (),
) -> None:
    """Add a normalized candidate if it clears basic structural checks."""
    clean_name = _clean_name(raw_name)
    clean_source = _clean_name(source_name)
    if not _is_valid_candidate(clean_name) or _early_reject(clean_name, acronym_anchors=acronym_anchors):
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


def _round_robin_terms(*groups: Sequence[str]) -> list[str]:
    """Interleave keyword groups so one source term does not dominate generation."""
    cleaned_groups = [[_clean_name(word) for word in group if _clean_name(word)] for group in groups]
    ordered: list[str] = []
    seen: set[str] = set()
    max_length = max((len(group) for group in cleaned_groups), default=0)
    for index in range(max_length):
        for group in cleaned_groups:
            if index >= len(group):
                continue
            word = group[index]
            if word in seen:
                continue
            seen.add(word)
            ordered.append(word)
    return ordered


def _deterministic_take(words: Sequence[str], limit: int) -> list[str]:
    """Pick a stable shuffled slice based on the current seeded RNG state."""
    pool = _ordered_unique([_clean_name(word) for word in words if _clean_name(word)])
    random.shuffle(pool)
    return pool[:limit]


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
        normalized_style = GENERATION_STYLE_ALIASES.get(normalized_style, normalized_style)
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
    if niche in {"Tech & SaaS", "Crypto & Web3"} or signal_terms & AI_SIGNAL_TERMS:
        styles.extend(["compound", "brandable", "invented", "short", "exact"])
    elif niche == "Finance & Fintech":
        styles.extend(["compound", "brandable", "exact", "short", "invented"])
    elif niche in {"Health & Medical", "Real Estate & Property", "Legal & Professional"}:
        styles.extend(["exact", "compound", "brandable", "short", "invented"])
    elif niche in {"Education & Learning", "Travel & Lifestyle"}:
        styles.extend(["brandable", "compound", "exact", "invented", "short"])
    else:
        styles.extend(["brandable", "compound", "exact", "short", "invented"])

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


def _has_awkward_acronym_overlap(left: str, right: str, acronym_anchors: Sequence[str]) -> bool:
    """Avoid acronym joins like mcp+prompt -> mcprompt that hide a harsh cluster."""
    if left not in acronym_anchors or not right or left[-1:] != right[:1] or len(right) < 2:
        return False
    return right[1] not in VOWELS


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


def _syllable_name(syllable_count: int = 3) -> str:
    """Build a pronounceable invented name from consonant-vowel syllables."""
    consonants = ("b", "c", "d", "f", "g", "j", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z")
    vowels = ("a", "e", "i", "o", "u")
    return "".join(random.choice(consonants) + random.choice(vowels) for _ in range(syllable_count))


def _blend_keywords(left: str, right: str) -> str:
    """Blend compact pieces from two different keywords."""
    left_part = _keyword_front(left)[: max(3, min(5, len(left)))]
    right_part = _brand_root(right)[: max(3, min(4, len(right)))]
    return _merge_parts(left_part, right_part)


def _build_mode_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    limit: int,
    builder,
) -> list[dict[str, str | bool]]:
    """Run a builder with local deduplication and a candidate cap."""
    results: list[dict[str, str | bool]] = []
    seen: set[str] = set()
    acronym_anchors = _keyword_acronym_anchors(user_keywords)

    def add(raw_name: str, method: str, source_name: str = "") -> None:
        clean_name = _clean_name(raw_name)
        clean_source = _clean_name(source_name)
        if (
            len(results) >= limit
            or not _is_valid_candidate(clean_name)
            or _early_reject(clean_name, acronym_anchors=acronym_anchors)
            or clean_name in seen
        ):
            return
        seen.add(clean_name)
        results.append(_candidate_record(clean_name, method, clean_source))

    builder(add, user_keywords, support_terms)
    return results


def _support_terms_for_niche(niche: str, word_banks: Mapping[str, Sequence[str]], user_keyword_count: int = 0) -> list[str]:
    """Derive deterministic support vocabulary from the selected niche and local word banks."""
    bank_categories = NICHE_BANKS.get(niche, ("abstract", "power"))
    bank_words: list[str] = []
    for category in bank_categories:
        bank_words.extend(word_banks.get(category, []))
    bank_words.extend(word_banks.get("premium_words", []))
    safe_prefixes = [word for word in word_banks.get("short_prefixes", []) if word not in WEAK_PREFIXES]

    if user_keyword_count >= 5:
        max_support = 12
    elif user_keyword_count >= 3:
        max_support = 18
    else:
        max_support = 28

    # كلمات دعم أكثر تنوعاً لتغذية كل الأنماط
    support_terms = _ordered_unique(
        [
            *_deterministic_take(NICHE_STATIC_TERMS.get(niche, ()), 14),
            *_deterministic_take(bank_words, 14),
            *_deterministic_take(safe_prefixes, 6),
        ]
    )
    return support_terms[:max_support]


def _build_exact_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    niche: str,
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate exact-match and descriptive keyword candidates."""
    heads = _ordered_unique([*COMMERCIAL_HEADS_BY_NICHE.get(niche, ()), *support_terms])

    def builder(add, u_kws: Sequence[str], s_terms: Sequence[str]) -> None:
        acronym_anchors = _keyword_acronym_anchors(u_kws)
        # Pass 1: user keywords priority
        for keyword in u_kws[:8]:
            add(keyword, "keyword")
            for head in heads[:12]:
                if head == keyword or head in keyword or keyword in head:
                    continue
                if not _has_awkward_acronym_overlap(keyword, head, acronym_anchors):
                    add(_merge_parts(keyword, head), "exact", source_name=keyword)
                add(_merge_parts(head, keyword), "exact_reverse", source_name=keyword)
                if len(keyword) <= 7:
                    front = _keyword_front(keyword)
                    if not _has_awkward_acronym_overlap(front, head, acronym_anchors):
                        add(_merge_parts(front, head), "descriptive", source_name=keyword)

        # Pass 2: cross user keywords
        for i, kw1 in enumerate(u_kws[:5]):
            for kw2 in u_kws[i + 1 : 6]:
                if kw1 == kw2:
                    continue
                add(_merge_parts(kw1, kw2), "exact_cross", source_name=kw1)
                add(_merge_parts(_keyword_front(kw1), kw2), "exact_cross", source_name=kw1)

        # Pass 3: support terms fallback
        for term in s_terms[:4]:
            for head in heads[:4]:
                if term == head or head in term:
                    continue
                add(_merge_parts(term, head), "exact_support", source_name=term)

    return _build_mode_candidates(user_keywords, support_terms, limit, builder)


def _build_compound_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate keyword + commercial-anchor compound names."""
    suffixes = _ordered_unique([*HYBRID_SUFFIXES, *support_terms])

    def builder(add, u_kws: Sequence[str], s_terms: Sequence[str]) -> None:
        acronym_anchors = _keyword_acronym_anchors(u_kws)
        for keyword in u_kws[:8]:
            root = _brand_root(keyword)
            for suffix in suffixes[:12]:
                if suffix in keyword:
                    continue
                if not _has_awkward_acronym_overlap(keyword, suffix, acronym_anchors):
                    add(_merge_parts(keyword, suffix), "compound", source_name=keyword)
                if not _has_awkward_acronym_overlap(root, suffix, acronym_anchors):
                    add(_merge_parts(root, suffix), "compound", source_name=keyword)
            # تركيبات عكسية: suffix + keyword
            for suffix in suffixes[:6]:
                if suffix in keyword:
                    continue
                add(_merge_parts(suffix, keyword), "compound_reverse", source_name=keyword)

        # Pass 2: support terms
        for term in s_terms[:4]:
            root = _brand_root(term)
            for suffix in suffixes[:4]:
                if suffix in term:
                    continue
                add(_merge_parts(term, suffix), "compound_support", source_name=term)

    return _build_mode_candidates(user_keywords, support_terms, limit, builder)


def _build_brandable_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate startup-style brandable candidates without requiring the LLM."""
    endings = _deterministic_take(BRANDABLE_SUFFIXES, 10)
    prefixes = _deterministic_take(BRANDABLE_PREFIXES, 10)

    def builder(add, u_kws: Sequence[str], s_terms: Sequence[str]) -> None:
        for keyword in u_kws[:8]:
            root = _brand_root(keyword)
            back = _keyword_back(keyword)[-3:]
            for ending in endings[:7]:
                add(_merge_parts(root, ending), "brandable", source_name=keyword)
            for prefix in prefixes[:5]:
                add(_merge_parts(prefix, back), "brandable", source_name=keyword)
            for partner in s_terms[:5]:
                partner_root = _brand_root(partner)
                if partner_root == root:
                    continue
                add(_merge_parts(root, partner_root[-2:]), "brandable", source_name=keyword)
            for prefix in prefixes[:4]:
                if prefix == keyword:
                    continue
                add(_merge_parts(prefix, root), "brandable", source_name=keyword)
            # تحويلات صوتية إضافية
            twisted = _twist_name(root)
            if twisted:
                add(twisted, "brandable_twist", source_name=keyword)
            # نهايات مبتكرة إضافية
            for ending in ("ify", "ly", "ux", "ai"):
                add(_merge_parts(root, ending), "brandable", source_name=keyword)

        if not u_kws:
            for term in s_terms[:6]:
                root = _brand_root(term)
                for ending in endings[:4]:
                    add(_merge_parts(root, ending), "brandable_support", source_name=term)

    return _build_mode_candidates(user_keywords, support_terms, limit, builder)


def _build_invented_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate fully invented pronounceable names with optional keyword roots."""

    def builder(add, u_kws: Sequence[str], s_terms: Sequence[str]) -> None:
        acronym_anchors = _keyword_acronym_anchors(u_kws)
        # Pass 1: user keywords
        for keyword in u_kws[:6]:
            root = _brand_root(keyword)
            for ending in _deterministic_take(INVENT_SUFFIXES, 6):
                candidate = _merge_parts(root, ending)
                if _is_pronounceable(candidate, acronym_anchors=acronym_anchors):
                    add(candidate, "invented", source_name=keyword)
            twisted = _twist_name(root)
            if _is_pronounceable(twisted, acronym_anchors=acronym_anchors):
                add(twisted, "invented", source_name=keyword)
            # تركيبات مخترعة مع prefixes
            for prefix in _deterministic_take(INVENT_PREFIXES, 3):
                candidate = _merge_parts(prefix, root[-2:])
                if _is_pronounceable(candidate, acronym_anchors=acronym_anchors):
                    add(candidate, "invented", source_name=keyword)
        for index, left in enumerate(u_kws[:5]):
            for right in u_kws[index + 1 : 6]:
                blended = _blend_keywords(left, right)
                if _is_pronounceable(blended, acronym_anchors=acronym_anchors):
                    add(blended, "invented_blend", source_name=left)

        # 20% max: pure random (only if keyword-rooted didn't fill)
        pure_random_cap = max(3, limit // 5)
        for _ in range(pure_random_cap):
            for candidate in (_invent_name(), _syllable_name()):
                if _is_pronounceable(candidate):
                    add(candidate, "invented_random")

    return _build_mode_candidates(user_keywords, support_terms, limit, builder)


def _build_short_candidates(
    user_keywords: Sequence[str],
    support_terms: Sequence[str],
    word_banks: Mapping[str, Sequence[str]],
    limit: int,
) -> list[dict[str, str | bool]]:
    """Generate compact short names from keyword roots and safe short prefixes."""
    safe_prefixes = [word for word in word_banks.get("short_prefixes", []) if word not in WEAK_PREFIXES]
    endings = _deterministic_take(SHORT_ENDINGS, 6)

    def builder(add, u_kws: Sequence[str], s_terms: Sequence[str]) -> None:
        acronym_anchors = _keyword_acronym_anchors(u_kws)
        for _ in range(max(limit // 3, 4)):
            candidate = _cvcv_name()
            if _is_pronounceable(candidate):
                add(candidate, "short", source_name="cvcv")

        u_roots = _ordered_unique([_brand_root(term)[:3] for term in u_kws])
        for root in u_roots:
            trimmed_root = root[:3]
            if trimmed_root in acronym_anchors:
                for ending in ("ai", "io", "ia"):
                    candidate = _merge_parts(trimmed_root, ending)
                    if 4 <= len(candidate) <= 7 and _is_pronounceable(candidate, acronym_anchors=acronym_anchors):
                        add(candidate, "short", source_name=root)
            for ending in endings[:6]:
                candidate = _merge_parts(trimmed_root, ending)
                if 4 <= len(candidate) <= 7 and _is_pronounceable(candidate, acronym_anchors=acronym_anchors):
                    add(candidate, "short", source_name=root)

        for keyword in u_kws[:6]:
            cut_name = _cut_name(keyword)
            if 4 <= len(cut_name) <= 7 and _is_pronounceable(cut_name, acronym_anchors=acronym_anchors):
                add(cut_name, "short", source_name=keyword)

        s_roots = _ordered_unique(
            [*_deterministic_take([_brand_root(term)[:3] for term in s_terms], 6), *_deterministic_take(safe_prefixes, 6)]
        )
        for root in s_roots:
            trimmed_root = root[:3]
            for ending in endings[:4]:
                candidate = _merge_parts(trimmed_root, ending)
                if 4 <= len(candidate) <= 7 and _is_pronounceable(candidate):
                    add(candidate, "short_support", source_name=root)

    return _build_mode_candidates(user_keywords, support_terms, limit, builder)


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

    def builder(add, u_kws: Sequence[str], s_terms: Sequence[str]) -> None:
        for geo in selected_geo_terms[:5]:
            for service in base_services[:8]:
                if service == geo:
                    continue
                add(_merge_parts(geo, service), "geo", source_name=geo)
            for suffix in ("flow", "group", "hub", "labs", "pro", "works", "zone"):
                add(_merge_parts(geo, suffix), "geo_brandable", source_name=geo)

    return _build_mode_candidates(user_keywords, support_terms, limit, builder)


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
        support_terms = _support_terms_for_niche(niche, word_banks, len(user_keywords))

        # Remove user keywords from support terms
        user_keyword_set = set(user_keywords)
        support_terms = [t for t in support_terms if t not in user_keyword_set]
        acronym_anchors = _keyword_acronym_anchors(user_keywords)
        primary_keyword_anchor = _primary_keyword_anchor(user_keywords)

        candidates: dict[str, dict[str, str | bool]] = {}
        # وضع Auto يولّد عدد أكبر من المرشحين لتغطية كل الأنماط بشكل أعمق
        is_auto = _normalize_requested_styles(requested_styles) == [AUTO_STYLE]
        if is_auto:
            per_mode_limit = max(15, min(num_per_tier + 10, 30))
        else:
            per_mode_limit = max(6, min(num_per_tier, 12))
        resolved_styles = _resolve_generation_styles(niche, user_keywords, geo_terms, requested_styles)

        candidate_sets: list[list[dict[str, str | bool]]] = []
        if "exact" in resolved_styles:
            candidate_sets.append(_build_exact_candidates(user_keywords, support_terms, niche, per_mode_limit + 5))
        if "compound" in resolved_styles:
            candidate_sets.append(_build_compound_candidates(user_keywords, support_terms, per_mode_limit + 5))
        if "brandable" in resolved_styles:
            candidate_sets.append(_build_brandable_candidates(user_keywords, support_terms, per_mode_limit + 3))
        if "invented" in resolved_styles:
            candidate_sets.append(_build_invented_candidates(user_keywords, support_terms, per_mode_limit + 2))
        if "short" in resolved_styles:
            candidate_sets.append(_build_short_candidates(user_keywords, support_terms, word_banks, max(8, per_mode_limit)))
        if "geo" in resolved_styles:
            candidate_sets.append(
                _build_geo_candidates(geo_terms, user_keywords, niche, support_terms, max(6, per_mode_limit - 2))
            )

        for candidate_group in candidate_sets:
            for candidate in candidate_group:
                _append_candidate(
                    candidates,
                    str(candidate.get("name") or ""),
                    str(candidate.get("method") or "combine"),
                    source_name=str(candidate.get("source_name") or ""),
                    acronym_anchors=acronym_anchors,
                )

        if use_llm:
            from providers.llm import llm_creative_boost

            llm_suggestions = llm_creative_boost(
                niche,
                list(candidates.keys()),
                selected_keywords=user_keywords,
                requested_styles=resolved_styles,
                geo_context=geo_context,
                count=max(num_per_tier * 2, len(user_keywords) * 3, 20)
                if is_auto
                else max(num_per_tier, len(user_keywords), 8),
            )
            for suggestion in llm_suggestions:
                _append_candidate(
                    candidates,
                    str(suggestion.get("name") or ""),
                    str(suggestion.get("method") or "llm"),
                    acronym_anchors=acronym_anchors,
                )

        keyword_anchored_candidates = _visible_keyword_filter(list(candidates.values()), primary_keyword_anchor)
        balanced_candidates = _style_balance_filter(keyword_anchored_candidates)
        return _diversity_filter(balanced_candidates, user_keywords=user_keywords)
    finally:
        random.setstate(random_state)
