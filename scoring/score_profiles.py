"""Profile definitions for domain scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreProfile:
    """Configuration for a resale-oriented domain scoring profile."""

    key: str
    label: str
    description: str
    preferred_tlds: dict[str, int]
    acceptable_tlds: dict[str, int]
    discouraged_tlds: set[str]
    favored_terms: set[str]
    generic_terms: set[str]
    head_terms: set[str]
    modifier_terms: set[str]
    commercial_terms: set[str]
    local_terms: set[str]
    exact_match_terms: set[str]


COMMON_GENERIC_TERMS = {
    "data", "pay", "flow", "stream", "stack", "labs", "logic", "vault", "cloud", "forge",
    "hub", "base", "works", "studio", "care", "clinic", "group", "grid", "drive", "edge",
    "relay", "trade", "fund", "wealth", "asset", "mint", "yield", "pixel", "canvas", "design",
    "prompt", "agent", "model", "bot", "mesh", "node", "link", "auth", "cache", "infra", "health",
}

COMMON_HEAD_TERMS = {
    "flow", "stream", "stack", "labs", "logic", "vault", "forge", "studio", "cloud", "hub",
    "base", "works", "care", "clinic", "fund", "health", "mesh", "node", "grid", "group",
    "bot", "agent", "model", "ai", "core", "space", "point", "relay", "trade", "pay",
}

COMMON_MODIFIER_TERMS = {
    "data", "pay", "prompt", "smart", "clear", "prime", "neo", "nova", "ultra", "fast",
    "mint", "trust", "secure", "open", "real", "local", "urban", "city", "cloud", "ai",
    "code", "pixel", "health", "wealth", "home", "legal", "tax", "roof", "clean", "repair",
}

COMMON_COMMERCIAL_TERMS = {
    "pay", "fund", "trade", "wealth", "asset", "care", "clinic", "legal", "tax", "repair",
    "clean", "roof", "home", "realty", "health", "loan", "credit", "cash", "deal", "store",
}

LOCAL_SERVICE_TERMS = {
    "plumbing", "plumber", "roof", "roofing", "clean", "cleaning", "care", "clinic", "dental",
    "legal", "law", "tax", "repair", "auto", "home", "realty", "med", "health", "locksmith",
}

EXACT_MATCH_TERMS = {
    "software", "tools", "cloud", "hosting", "repair", "cleaning", "clinic", "legal", "tax",
    "data", "analytics", "payments", "pay", "fund", "credit", "health", "realty", "homes",
}

PROFILE_MAP: dict[str, ScoreProfile] = {
    "startup_brand": ScoreProfile(
        key="startup_brand",
        label="Startup Brand",
        description="Balanced brandability and resale quality for startup-ready names.",
        preferred_tlds={".com": 10, ".io": 9, ".ai": 8, ".co": 8, ".app": 7},
        acceptable_tlds={".dev": 6, ".net": 5, ".org": 4},
        discouraged_tlds=set(),
        favored_terms={"labs", "forge", "stack", "cloud", "flow", "data", "vault", "logic", "node"},
        generic_terms=COMMON_GENERIC_TERMS,
        head_terms=COMMON_HEAD_TERMS,
        modifier_terms=COMMON_MODIFIER_TERMS,
        commercial_terms=COMMON_COMMERCIAL_TERMS,
        local_terms=LOCAL_SERVICE_TERMS,
        exact_match_terms=EXACT_MATCH_TERMS,
    ),
    "ai_brand": ScoreProfile(
        key="ai_brand",
        label="AI Brand",
        description="AI-native brands for tooling, model infra, agents, and applied AI startups.",
        preferred_tlds={".ai": 10, ".com": 9, ".io": 8, ".dev": 7, ".app": 7},
        acceptable_tlds={".co": 6, ".net": 4, ".org": 4},
        discouraged_tlds={".org"},
        favored_terms={"ai", "agent", "prompt", "model", "data", "bot", "cloud", "stack", "forge", "labs"},
        generic_terms=COMMON_GENERIC_TERMS | {"agent", "prompt", "model", "train", "vector", "token"},
        head_terms=COMMON_HEAD_TERMS | {"agent", "model", "bot", "vector"},
        modifier_terms=COMMON_MODIFIER_TERMS | {"prompt", "data", "auto", "smart", "agent", "model"},
        commercial_terms=COMMON_COMMERCIAL_TERMS | {"ai", "agent"},
        local_terms=LOCAL_SERVICE_TERMS,
        exact_match_terms=EXACT_MATCH_TERMS | {"ai", "agents", "automation"},
    ),
    "flip_fast": ScoreProfile(
        key="flip_fast",
        label="Flip Fast",
        description="High-liquidity names optimized for quick resale appeal.",
        preferred_tlds={".com": 10, ".io": 7, ".co": 6, ".ai": 6},
        acceptable_tlds={".net": 4, ".org": 3, ".app": 4, ".dev": 3},
        discouraged_tlds={".org", ".dev"},
        favored_terms={"pay", "data", "flow", "vault", "labs", "cloud", "fund", "care", "health"},
        generic_terms=COMMON_GENERIC_TERMS,
        head_terms=COMMON_HEAD_TERMS,
        modifier_terms=COMMON_MODIFIER_TERMS,
        commercial_terms=COMMON_COMMERCIAL_TERMS,
        local_terms=LOCAL_SERVICE_TERMS,
        exact_match_terms=EXACT_MATCH_TERMS,
    ),
    "geo_local": ScoreProfile(
        key="geo_local",
        label="Geo Local",
        description="Location-driven local service and small-business domain fit.",
        preferred_tlds={".com": 10, ".co": 6, ".org": 5, ".net": 5},
        acceptable_tlds={".ai": 2, ".io": 2, ".app": 3, ".dev": 2},
        discouraged_tlds={".ai", ".io", ".dev"},
        favored_terms={"city", "local", "home", "care", "clinic", "legal", "tax", "repair", "roof"},
        generic_terms=COMMON_GENERIC_TERMS | LOCAL_SERVICE_TERMS,
        head_terms=COMMON_HEAD_TERMS | {"home", "realty", "clinic", "legal", "repair"},
        modifier_terms=COMMON_MODIFIER_TERMS | {"local", "city", "urban", "metro", "home"},
        commercial_terms=COMMON_COMMERCIAL_TERMS | LOCAL_SERVICE_TERMS,
        local_terms=LOCAL_SERVICE_TERMS,
        exact_match_terms=EXACT_MATCH_TERMS | LOCAL_SERVICE_TERMS,
    ),
    "seo_exact": ScoreProfile(
        key="seo_exact",
        label="SEO Exact",
        description="Clear exact-match and commercial-intent combinations.",
        preferred_tlds={".com": 10, ".net": 7, ".org": 6, ".co": 6},
        acceptable_tlds={".ai": 4, ".io": 3, ".app": 4, ".dev": 3},
        discouraged_tlds={".io", ".dev"},
        favored_terms={"tools", "data", "cloud", "repair", "clinic", "legal", "tax", "homes", "health"},
        generic_terms=COMMON_GENERIC_TERMS | EXACT_MATCH_TERMS,
        head_terms=COMMON_HEAD_TERMS | {"tools", "software", "repair", "clinic", "legal"},
        modifier_terms=COMMON_MODIFIER_TERMS | {"best", "local", "online", "data", "cloud"},
        commercial_terms=COMMON_COMMERCIAL_TERMS | EXACT_MATCH_TERMS,
        local_terms=LOCAL_SERVICE_TERMS,
        exact_match_terms=EXACT_MATCH_TERMS | {"tools", "software", "services", "solutions"},
    ),
}


def get_profile(profile: str) -> ScoreProfile:
    """Return a scoring profile configuration, defaulting to startup brand."""
    return PROFILE_MAP.get(profile, PROFILE_MAP["startup_brand"])
