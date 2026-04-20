"""Shared application constants for the Streamlit app."""

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
    "Tech & AI",
    "Finance & SaaS",
    "E-commerce",
    "Creative & Arts",
    "Health & Wellness",
    "Real Estate",
]

SCORING_PROFILES = [
    "startup_brand",
    "ai_brand",
    "flip_fast",
    "geo_local",
    "seo_exact",
]
DEFAULT_SCORING_PROFILE = "startup_brand"

DEFAULT_EXTENSIONS = [".com", ".ai"]
EXTENSION_OPTIONS = [".com", ".net", ".org", ".io", ".ai", ".co", ".app", ".dev"]
GENERATION_STYLE_OPTIONS = [
    "auto",
    "exact",
    "brandable",
    "ai_futuristic",
    "hybrid",
    "short",
    "outbound",
    "geo",
]
GENERATION_STYLE_LABELS = {
    "auto": "Auto",
    "exact": "Exact / Descriptive",
    "brandable": "Brandable",
    "ai_futuristic": "AI / Futuristic",
    "hybrid": "Hybrid",
    "short": "Short",
    "outbound": "Outbound",
    "geo": "Geo",
}

PORTFOLIO_STATUS_UNCHECKED = "Not checked"
SUPABASE_ENABLED = _SETTINGS.supabase_enabled
