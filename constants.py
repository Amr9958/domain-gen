"""Shared application constants for the Streamlit app."""

APP_TITLE = "DomainTrade Pro V5"
APP_ICON = "🔥"
APP_LAYOUT = "wide"
DB_PATH = "domains.db"
WORD_BANKS_DIR = "word_banks"

AI_PROVIDERS = ["xAI (Grok)", "Google Gemini", "OpenRouter"]
DEFAULT_AI_PROVIDER = "xAI (Grok)"

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

PORTFOLIO_STATUS_UNCHECKED = "Not checked"
