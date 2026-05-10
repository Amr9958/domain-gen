"""Shared application constants for the Streamlit app."""

from __future__ import annotations

from dataclasses import dataclass

from config import get_settings


_SETTINGS = get_settings()

APP_TITLE = _SETTINGS.app_title
APP_ICON = _SETTINGS.app_icon
APP_LAYOUT = _SETTINGS.app_layout
DB_PATH = str(_SETTINGS.local_db_path)
WORD_BANKS_DIR = str(_SETTINGS.word_banks_dir)

AI_PROVIDERS = ["xAI (Grok)", "Google Gemini", "OpenRouter"]
DEFAULT_AI_PROVIDER = _SETTINGS.default_ai_provider

NICHE_OPTIONS = [
    "Tech & SaaS",
    "Finance & Fintech",
    "E-commerce & Retail",
    "Travel & Lifestyle",
    "Health & Medical",
    "Real Estate & Property",
    "Education & Learning",
    "Legal & Professional",
    "Crypto & Web3",
]

DEFAULT_EXTENSIONS = [".com", ".ai"]
EXTENSION_OPTIONS = [".com", ".net", ".org", ".io", ".ai", ".co", ".app", ".dev"]


@dataclass(frozen=True)
class GenerationStyle:
    """Single source of truth for generation style metadata."""

    key: str
    label: str
    description: str
    llm_guidance: str


AUTO_STYLE = "auto"
GENERATION_STYLES = {
    "exact": GenerationStyle(
        key="exact",
        label="Exact / Descriptive",
        description="Keyword + head term. Direct, descriptive, and buyer-clear.",
        llm_guidance="Exact-match or descriptive names with clear buyer intent and commercial clarity.",
    ),
    "brandable": GenerationStyle(
        key="brandable",
        label="Brandable",
        description="A startup-ready name derived from the keywords.",
        llm_guidance="Fundable startup-style brandables that sound like real products or companies.",
    ),
    "compound": GenerationStyle(
        key="compound",
        label="Compound",
        description="Keyword + anchor suffix such as hub, flow, labs, forge, or stack.",
        llm_guidance="Compound names that pair a commercial keyword with a credible anchor suffix or prefix.",
    ),
    "short": GenerationStyle(
        key="short",
        label="Short",
        description="Four to six letters with clean phonetics and memorability.",
        llm_guidance="Short premium-feeling names with clean phonetics and strong memorability.",
    ),
    "invented": GenerationStyle(
        key="invented",
        label="Invented",
        description="Fully invented pronounceable names without a direct literal meaning.",
        llm_guidance="Invented but pronounceable names that feel ownable, credible, and startup-usable.",
    ),
    "geo": GenerationStyle(
        key="geo",
        label="Geo",
        description="Location + service names for local opportunities with explicit geo context.",
        llm_guidance="Geo-targeted names only when the provided keywords or geo context include a real place.",
    ),
}
GENERATION_STYLE_ORDER = tuple(GENERATION_STYLES.keys())
GENERATION_STYLE_OPTIONS = [AUTO_STYLE, *GENERATION_STYLE_ORDER]
GENERATION_STYLE_LABELS = {
    AUTO_STYLE: "Auto",
    **{key: style.label for key, style in GENERATION_STYLES.items()},
}

PORTFOLIO_STATUS_UNCHECKED = "Not checked"
SUPABASE_ENABLED = _SETTINGS.supabase_enabled
