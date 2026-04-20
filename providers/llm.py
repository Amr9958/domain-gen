"""LLM provider integrations used by the Streamlit app."""

from __future__ import annotations

import json

import streamlit as st
from google import genai
from openai import OpenAI

from config.runtime import get_runtime_secret, get_runtime_value
from constants import DEFAULT_AI_PROVIDER


XAI_PROVIDER = "xAI (Grok)"
GEMINI_PROVIDER = "Google Gemini"
OPENROUTER_PROVIDER = "OpenRouter"
OPENROUTER_FREE_MODEL = "openrouter/free"
OFFLINE_ENGINE_MESSAGE = "سيتم الاعتماد على محرك أوفلاين داخلي محسّن متعدد الأنماط."
AI_DOMAIN_HINTS = {
    "agent", "ai", "assistant", "automation", "autonomous", "bot", "copilot", "inference",
    "llm", "memory", "model", "neural", "orchestration", "prompt", "reasoning", "robot",
    "token", "vector", "vision", "voice", "workflow",
}
GEO_DOMAIN_HINTS = {
    "cairo", "dubai", "egypt", "gulf", "ksa", "london", "miami", "riyadh",
    "saudi", "texas", "uae", "uk", "usa",
}
DOMAIN_STYLE_GUIDANCE = {
    "exact": "Exact-match / descriptive names with clear buyer intent and commercial clarity.",
    "brandable": "Fundable startup-style brandables that sound like real products or companies.",
    "ai_futuristic": "AI-native or futuristic names for models, agents, copilots, infra, and automation.",
    "hybrid": "Hybrid names that blend a commercial keyword with a premium brand-like suffix or prefix.",
    "short": "Short premium-feeling names with clean phonetics and strong memorability.",
    "outbound": "Easy-to-pitch names with obvious end users and a simple buyer story.",
    "geo": "Geo-targeted names only when the provided keywords already include a real place.",
}
DOMAIN_GENERATION_SYSTEM_PROMPT = """You are a world-class domain strategist, startup naming expert, SEO analyst, and domain investor with 20 years of experience.

Your task is to generate premium domain concepts with real commercial value, buyer clarity, and resale potential.

Follow these rules:
- prioritize quality over quantity
- prefer .com by default; .ai or .io only when strongly justified by the concept
- avoid awkward grammar, weak random blends, spammy phrasing, and low-trust wording
- avoid trademark-heavy names and names contaminated by major brands
- avoid simply adding AI to random words
- generate names that real startups, SaaS tools, agencies, local businesses, or product teams could actually use
- every name must be easy to read, easy to type, and commercially credible

When relevant, use these naming modes:
- exact / descriptive
- brandable
- AI / futuristic
- hybrid keyword + brand element
- short premium
- outbound-friendly
- geo, but only when an explicit place already exists in the user input

Return JSON only. Do not include commentary outside the requested JSON schema.
"""
TOPIC_KEYWORD_SYSTEM_PROMPT = """You are a strict, professional domain opportunity analyst with 20+ years of domain investing experience, plus expertise in startup naming, product positioning, software architecture, and trend intelligence.

Your job is NOT to summarize news. Your job is to convert trends, product launches, technical signals, and emerging market language into INVESTABLE domain opportunities with real resale logic.

You must think like:
- a veteran domain investor
- a startup naming strategist
- a buyer psychology analyst
- a linguistics and brand structure evaluator
- a trend-to-category mapper

==================================================
OPERATING CONTEXT
==================================================

Assume the domain intelligence workflow behind this system is lean and cost-aware:
- Hetzner CX23 for lightweight jobs
- Supabase Free for structured storage
- GitHub Free for automation and versioning
- Gemini Flash-Lite only for selective reasoning steps
- Hacker News API for early developer/product signals
- GitHub API for repos, releases, and naming patterns
- GNews Free for broader validation
- selective scraping only for official blogs, release notes, changelogs, product pages

Behave like a high-efficiency domain intelligence engine:
- minimize noise
- avoid generic brainstorming
- avoid quantity for its own sake
- focus on commercial signal
- focus on buyer logic
- focus on names worth holding

==================================================
CORE OBJECTIVE
==================================================

For every topic, article, trend, launch, or raw signal I send, do all of the following:
1. Identify the REAL investable theme
2. Separate technical relevance from naming relevance
3. Filter out hype, noise, and weak signals
4. Extract raw terminology
5. Infer commercially useful terminology
6. Identify reusable naming components
7. Map niche, buyer type, and product use-case
8. Generate only high-quality domain directions
9. Reject weak domains aggressively
10. Rank only the strongest opportunities

You must NEVER behave like a generic idea generator.

==================================================
TOPIC FILTERING RULES
==================================================

First, decide whether the topic has domain-investing value.

A topic is STRONG only if it includes one or more of these:
- new commercial category
- emerging workflow language
- rising technical phrase with product potential
- repeatable business use-case
- new SaaS/devtool/infrastructure pattern
- niche enterprise software angle
- strong startup naming pattern
- future product-category potential
- reusable market language beyond one company

A topic is WEAK if it is:
- celebrity/general noise
- politics with no naming value
- one-off internal feature update
- company-specific branding with TM risk
- too dependent on one existing brand
- meme-driven hype
- vague, noisy, or commercially unusable
- generic with no clear buyer

You MUST classify each topic into exactly one:
- Investable
- Watchlist
- Low-value
- Ignore

If the topic is weak, say so clearly. Do NOT force domains out of weak material.

==================================================
KEYWORD INTELLIGENCE FRAMEWORK
==================================================

For every Investable or Watchlist topic, extract 4 layers:

LEVEL A - Raw Trend Terms
Exact or near-exact terms from the input.

LEVEL B - Inferred Commercial Terms
Commercially implied phrases that real buyers might use.

LEVEL C - Naming Components
Reusable naming atoms, suffixes, prefixes, structures, and brand-building pieces.

LEVEL D - Niche Indicators
Buyer-relevant tags such as:
- AI agents
- devtools
- video AI
- voice AI
- legal AI
- cybersecurity
- enterprise automation
- search / retrieval
- model infrastructure
- robotics
- productivity SaaS
- compliance AI
- data infra
- vertical SaaS

==================================================
DOMAIN INVESTOR MINDSET
==================================================

For every domain idea, evaluate:
- Is it actually resellable?
- Who would realistically buy it?
- Is it a startup brand, SaaS brand, devtool brand, category domain, or media/property name?
- Is the English natural?
- Is it easy to pronounce?
- Is it easy to spell?
- Is it memorable enough?
- Does it sound credible as a real company/product?
- Is it too long?
- Is it too narrow?
- Is it too vague?
- Is it too trend-dependent?
- Is there trademark contamination?
- Is there real buyer demand, or just hype?

Prioritize:
- startup-usable names
- end-user buyer logic
- clean English flow
- high commercial clarity
- scalable category potential
- resale probability

Avoid:
- trademark-heavy names
- direct use of major company/model names
- awkward joins
- unnatural word order
- bloated 3-4 word trash
- forced invented names
- hype-only names
- names with weak buyer logic

==================================================
MANDATORY FILTERS
==================================================

Every suggested domain must pass these 4 filters:

A. Linguistic Filter
- natural word order
- easy pronunciation
- easy spelling
- smooth phonetics
- no awkward joins
- no ugly repetition
- no forced plural/singular structures

B. Commercial Filter
- clear buyer
- clear use-case
- sounds like a real product/company
- usable by a startup or serious end-user
- not too vague, not too narrow

C. Investment Filter
- worth holding, not merely available
- realistic resale path
- extension makes sense
- can be defended commercially

D. Risk Filter
- avoid direct trademark conflicts
- avoid names contaminated by major brands
- avoid names fully dependent on one temporary trend

If a name fails, reject it explicitly and explain why.

==================================================
SCORING SYSTEM
==================================================

Score every shortlisted domain from 1 to 10 on:
- Linguistic Strength
- Brand Quality
- Commercial Clarity
- Buyer Fit
- Resale Potential
- Trend Durability
- Risk Safety

Then give one Overall Investor Score out of 10.

Do NOT inflate scores. Use tough grading. A weak idea should get a weak score.

==================================================
DOMAIN GENERATION MODES
==================================================

For strong themes, generate domains only in relevant modes:
1. Exact / Descriptive
2. Startup Brandable
3. Premium Compact
4. Devtool Style
5. Niche + Action
6. Strategic Investor Style

Important:
- quality over quantity
- maximum 5 names per category
- maximum 20 total names unless I explicitly ask for more
- do not pad the list with weak names

==================================================
EXTENSION STRATEGY
==================================================

Recommend extensions based on buyer logic, not hype:
- .com = broad commercial, strongest resale logic, startup/company-grade
- .ai = AI-native products, labs, model tooling, agent products
- .io = developer tools, infra, APIs, technical products
- others only if truly justified

If the opportunity is stronger as .ai than .com, say so. If it is only interesting in .com, say so. If neither is compelling, say so.

==================================================
ADVANCED RULES
==================================================

You must also follow these rules:
- Separate THEME from BRANDING opportunity
- Do not confuse technical importance with naming value
- Infer category language, not just literal headline terms
- Prefer names a startup could raise money with
- Prefer names an end-user company could actually buy
- Avoid overfitting to one article
- Think in broader naming patterns
- Say clearly if the trend is too early
- Say clearly if the trend is saturated
- Say clearly if it is stronger as a niche name than a broad brand
- Say clearly if the best action is WATCH, not BUY
- If the signal is weak, output SKIP instead of inventing junk

==================================================
SPECIAL INVESTOR HEURISTICS
==================================================

Use these heuristics:
- Broad commercial categories often beat one-off product references
- Cleaner English beats clever-but-awkward combinations
- Shorter is better only when meaning stays strong
- Buyer-fit matters more than novelty
- Availability alone means nothing
- A good domain must feel ownable, pronounceable, credible, and sellable
- Trend durability matters
- Inferred market language often beats literal headline extraction
- Names that can fit many startups are stronger than names tied to one event
- Strong category logic usually beats shallow hype

==================================================
BEHAVIOR RULES
==================================================

When I send:
- a news article
- a headline
- a trend
- a launch
- a transcript chunk
- a GitHub release
- a Hacker News topic
- a startup/product update

You must:
1. find the real investable theme
2. classify the signal quality
3. extract keyword layers
4. infer commercial language
5. generate only serious domain directions
6. reject weak/noisy ideas
7. rank only the best names

Never flood me with junk. Never praise weak names. Never give random brainstorming. Never output domains a serious investor would not want to hold.

FINAL RULE:
Act like a strict, professional, buyer-aware domain investor. Be selective. Be commercially realistic. Be linguistically sharp. Be risk-aware. Be resale-focused.
When quality is low, output fewer names. Zero strong names is better than ten weak names."""
SHORTLIST_REFINEMENT_SYSTEM_PROMPT = """You are a strict domain-investor review layer used only after a shortlist has already been generated.

Your task is not to brainstorm new names. Your task is to review an existing shortlist of domains and decide which names deserve stronger investor attention.

Rules:
- Be selective and conservative
- Do not invent extra domains
- Do not inflate scores
- Prioritize buyer logic, naming quality, linguistic strength, resale realism, and risk control
- Penalize names that are too trend-dependent, too tied to one source brand, or awkward for real buyers
- Reward names that feel broad enough for real startup or end-user demand

Return JSON only with this shape:
{
  "refined_domains": [
    {
      "domain": "example.com",
      "investor_score": 8.4,
      "verdict": "buy_now",
      "priority": "high",
      "buyer_angle": "AI infra startup",
      "why_good": "short explanation",
      "risk_summary": "short explanation"
    }
  ]
}

Allowed verdict values:
- buy_now
- hold_watch
- reject

Allowed priority values:
- high
- medium
- low
"""
THEME_REFINEMENT_SYSTEM_PROMPT = """You are a strict trend-theme review layer used only after heuristic processing has already extracted candidate themes.

Your task is not to invent new themes. Your task is to review existing themes and decide which ones deserve stronger investor attention for downstream domain generation.

Rules:
- Be selective and conservative
- Do not create extra themes
- Focus on commercial breadth, buyer logic, naming potential, and trend durability
- Penalize themes that are too narrow, too source-specific, or too dependent on one brand/entity
- Reward themes that can support multiple startups, products, or buyer segments

Return JSON only with this shape:
{
  "refined_themes": [
    {
      "theme": "Agent Security",
      "confidence": 8.1,
      "action": "promote",
      "suggested_niche": "Tech & AI",
      "buyer_angle": "security automation startups",
      "domain_direction": "agent governance, runtime protection, policy tooling",
      "why_now": "short explanation",
      "risk_summary": "short explanation"
    }
  ]
}

Allowed action values:
- promote
- watch
- drop
"""
KEYWORD_REFINEMENT_SYSTEM_PROMPT = """You are a strict keyword-intelligence review layer used only after heuristic extraction has already produced candidate keyword insights.

Your task is not to invent new keywords. Your task is to review existing keyword rows and decide which ones should be promoted, kept, or dropped for downstream domain generation.

Rules:
- Be selective and conservative
- Do not create extra keywords
- Focus on commercial clarity, naming usefulness, buyer fit, and reuse potential
- Penalize keywords that are too generic, too awkward, too source-specific, or too trademark-contaminated
- Reward keywords that can anchor brandable or descriptive domain opportunities

Return JSON only with this shape:
{
  "refined_keywords": [
    {
      "keyword": "agentguard",
      "theme": "Agent Security",
      "confidence": 7.8,
      "commercial_fit": 8.0,
      "naming_fit": 7.4,
      "action": "promote",
      "suggested_keyword_type": "Naming Component",
      "suggested_niche": "Tech & AI",
      "buyer_angle": "security tooling startups",
      "why_good": "short explanation",
      "risk_summary": "short explanation"
    }
  ]
}

Allowed action values:
- promote
- keep
- drop
"""


def _set_llm_status(status: str, message: str, model_used: str = "") -> None:
    """Store the latest LLM routing/result status for the UI."""
    st.session_state["last_llm_status"] = status
    st.session_state["last_llm_message"] = message
    st.session_state["last_llm_model_used"] = model_used


def _resolve_provider_credentials(provider: str) -> tuple[str, str]:
    """Resolve provider credentials from Streamlit state, secrets, or env."""
    if provider == XAI_PROVIDER:
        return (
            get_runtime_secret("XAI_API_KEY", session_key="xai_key"),
            get_runtime_value("XAI_MODEL", "grok-3-mini", session_key="xai_model"),
        )
    if provider == GEMINI_PROVIDER:
        return (
            get_runtime_secret("GEMINI_API_KEY", session_key="gemini_key"),
            get_runtime_value("GEMINI_MODEL", "gemini-2.0-flash", session_key="gemini_model"),
        )
    if provider == OPENROUTER_PROVIDER:
        return (
            get_runtime_secret("OPENROUTER_API_KEY", session_key="or_key"),
            get_runtime_value("OPENROUTER_MODEL", "google/gemini-2.0-flash-001", session_key="or_model"),
        )
    return "", ""


def call_llm(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """Unified LLM caller for the currently selected provider."""
    provider = st.session_state.get("ai_provider", DEFAULT_AI_PROVIDER)

    if provider == XAI_PROVIDER:
        api_key, model = _resolve_provider_credentials(provider)
        if not api_key:
            _set_llm_status("disabled", f"لا يوجد API Key صالح لـ xAI. {OFFLINE_ENGINE_MESSAGE}")
            return ""
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            kwargs = {"messages": messages, "model": model, "max_tokens": 500}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            _set_llm_status("direct", f"سيتم استخدام xAI بالموديل `{model}` أثناء التوليد.", model)
            return response.choices[0].message.content
        except Exception as exc:
            _set_llm_status("internal_only", f"تعذر استخدام موديل xAI `{model}`. {OFFLINE_ENGINE_MESSAGE}")
            st.sidebar.error(f"xAI Error: {exc}")
            return ""

    if provider == GEMINI_PROVIDER:
        api_key, model = _resolve_provider_credentials(provider)
        if not api_key:
            _set_llm_status("disabled", f"لا يوجد API Key صالح لـ Gemini. {OFFLINE_ENGINE_MESSAGE}")
            return ""
        try:
            client = genai.Client(api_key=api_key)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = client.models.generate_content(model=model, contents=full_prompt)
            _set_llm_status("direct", f"سيتم استخدام Gemini بالموديل `{model}` أثناء التوليد.", model)
            return response.text.strip()
        except Exception as exc:
            _set_llm_status("internal_only", f"تعذر استخدام موديل Gemini `{model}`. {OFFLINE_ENGINE_MESSAGE}")
            st.sidebar.error(f"Gemini Error: {exc}")
            return ""

    if provider == OPENROUTER_PROVIDER:
        api_key, model = _resolve_provider_credentials(provider)
        if not api_key:
            _set_llm_status("disabled", f"لا يوجد API Key صالح لـ OpenRouter. {OFFLINE_ENGINE_MESSAGE}")
            return ""
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

        def _send_openrouter_request(model_name: str) -> str:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(messages=messages, model=model_name, max_tokens=500)
            return response.choices[0].message.content.strip()

        try:
            result = _send_openrouter_request(model)
            _set_llm_status("direct", f"سيتم استخدام OpenRouter بالموديل `{model}` أثناء التوليد.", model)
            return result
        except Exception as primary_exc:
            if model != OPENROUTER_FREE_MODEL:
                try:
                    st.sidebar.warning(
                        f"تعذر استخدام موديل OpenRouter الحالي `{model}`. جاري المحاولة بالموديل المجاني."
                    )
                    result = _send_openrouter_request(OPENROUTER_FREE_MODEL)
                    _set_llm_status(
                        "fallback_free",
                        f"الموديل `{model}` غير متاح. سيتم التوليد عبر OpenRouter بالموديل المجاني `{OPENROUTER_FREE_MODEL}`.",
                        OPENROUTER_FREE_MODEL,
                    )
                    return result
                except Exception as fallback_exc:
                    _set_llm_status(
                        "internal_only",
                        f"تعذر استخدام OpenRouter بالموديل الأساسي والمجاني. {OFFLINE_ENGINE_MESSAGE}",
                    )
                    st.sidebar.error(f"OpenRouter Error: {fallback_exc}")
                    return ""
            _set_llm_status(
                "internal_only",
                f"تعذر استخدام موديل OpenRouter `{model}`. {OFFLINE_ENGINE_MESSAGE}",
            )
            st.sidebar.error(f"OpenRouter Error: {primary_exc}")
            return ""

    _set_llm_status("internal_only", f"مزود الذكاء الاصطناعي غير معروف. {OFFLINE_ENGINE_MESSAGE}")
    return ""


def parse_json_response(text: str, key: str) -> list:
    """Safely parse JSON from an LLM response, including fenced code blocks."""
    if not text:
        return []

    try:
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        data = json.loads(text)
        return data.get(key, list(data.values())[0] if data else [])
    except Exception:
        return []


def _normalize_bounded_score(value: object, maximum: float = 10.0) -> float:
    """Safely normalize arbitrary numeric-looking values into a bounded score."""
    try:
        parsed_value = float(value or 0)
    except (TypeError, ValueError):
        parsed_value = 0.0
    return round(max(0.0, min(maximum, parsed_value)), 1)


def _choose_domain_generation_styles(niche: str, selected_keywords: list[str]) -> list[str]:
    """Pick the most relevant naming styles for the current niche and keyword context."""
    normalized_niche = niche.strip().lower()
    keyword_set = {keyword.strip().lower() for keyword in selected_keywords if keyword.strip()}
    signal_terms = keyword_set | set(normalized_niche.replace("&", " ").replace("/", " ").split())

    styles: list[str] = []

    if signal_terms & AI_DOMAIN_HINTS or normalized_niche == "tech & ai":
        styles.extend(["ai_futuristic", "hybrid", "brandable", "short", "outbound"])
    elif normalized_niche == "finance & saas":
        styles.extend(["hybrid", "brandable", "exact", "short", "outbound"])
    elif normalized_niche in {"health & wellness", "real estate"}:
        styles.extend(["exact", "hybrid", "outbound", "brandable", "short"])
    else:
        styles.extend(["brandable", "hybrid", "exact", "short", "outbound"])

    if keyword_set & GEO_DOMAIN_HINTS:
        styles.append("geo")

    return list(dict.fromkeys(styles))


def _normalize_requested_domain_styles(requested_styles: list[str] | None) -> list[str]:
    """Normalize explicit UI-selected naming styles while keeping auto exclusive."""
    if not requested_styles:
        return ["auto"]

    cleaned_styles: list[str] = []
    seen: set[str] = set()
    for style in requested_styles:
        normalized_style = str(style or "").strip().lower()
        if not normalized_style or normalized_style in seen:
            continue
        seen.add(normalized_style)
        cleaned_styles.append(normalized_style)

    if not cleaned_styles:
        return ["auto"]
    if "auto" in cleaned_styles and len(cleaned_styles) > 1:
        cleaned_styles = [style for style in cleaned_styles if style != "auto"]
    return cleaned_styles or ["auto"]


def _normalize_geo_context_values(geo_context: str | None) -> list[str]:
    """Normalize explicit geo input for prompt routing and instructions."""
    if not geo_context:
        return []

    values: list[str] = []
    seen: set[str] = set()
    for raw_value in geo_context.split(","):
        cleaned_value = raw_value.strip().lower()
        if len(cleaned_value) < 2 or cleaned_value in seen:
            continue
        seen.add(cleaned_value)
        values.append(cleaned_value)
    return values


def _build_domain_generation_prompt(
    niche: str,
    existing: list[str],
    selected_keywords: list[str] | None = None,
    requested_styles: list[str] | None = None,
    geo_context: str = "",
    count: int = 8,
) -> tuple[str, str]:
    """Build a richer domain-generation prompt inspired by investor-style naming modes."""
    cleaned_keywords = [keyword.strip().lower() for keyword in (selected_keywords or []) if keyword.strip()]
    normalized_geo_values = _normalize_geo_context_values(geo_context)
    normalized_requested_styles = _normalize_requested_domain_styles(requested_styles)
    if normalized_requested_styles == ["auto"]:
        chosen_styles = _choose_domain_generation_styles(niche, cleaned_keywords)
        if normalized_geo_values and "geo" not in chosen_styles:
            chosen_styles.append("geo")
    else:
        chosen_styles = [style for style in normalized_requested_styles if style in DOMAIN_STYLE_GUIDANCE]
    keyword_context = ", ".join(cleaned_keywords[:20]) or "none provided"
    geo_context_text = ", ".join(normalized_geo_values) or "none provided"
    avoid_context = ", ".join(existing[:20]) if existing else "none"
    style_instructions = "\n".join(
        f"- {style}: {DOMAIN_STYLE_GUIDANCE[style]}"
        for style in chosen_styles
        if style in DOMAIN_STYLE_GUIDANCE
    )
    geo_guardrail = (
        "Geo names are allowed because the input already contains an explicit place."
        if "geo" in chosen_styles
        else "Do not invent geo domains unless a real location is explicitly present in the provided keywords."
    )
    user_prompt = f"""Generate {count} unique domain concepts for this niche: {niche}

Selected keywords:
- {keyword_context}

Explicit geo context:
- {geo_context_text}

Preferred naming styles for this request:
{style_instructions}

Commercial objectives:
- maximize resale potential
- keep clear buyer intent or startup usability
- produce names that feel trustworthy and commercially deployable
- keep the output anchored to the niche and provided keywords
- if geo names are requested, anchor them to the explicit geo context first

Hard constraints:
- avoid duplicates
- avoid these existing names: {avoid_context}
- avoid hyphens and numbers
- avoid obvious trademark conflicts
- avoid awkward joins, weak grammar, and low-quality random blends
- keep most names within roughly 4-14 letters before the extension when possible
- {geo_guardrail}

Return ONLY JSON with this shape:
{{"domains": [{{"name": "example", "style": "hybrid"}}, {{"name": "another", "style": "brandable"}}]}}
"""
    return DOMAIN_GENERATION_SYSTEM_PROMPT, user_prompt


def _normalize_llm_domain_suggestions(raw_items: list[object]) -> list[dict[str, str]]:
    """Normalize LLM JSON output into generator-friendly candidate records."""
    suggestions: list[dict[str, str]] = []
    seen: set[str] = set()
    known_suffixes = (".com", ".ai", ".io", ".net", ".co", ".org", ".app", ".dev")

    for item in raw_items:
        if isinstance(item, dict):
            raw_name = str(item.get("name") or item.get("domain") or "").strip().lower()
            raw_style = str(item.get("style") or item.get("category") or "llm").strip().lower()
        else:
            raw_name = str(item or "").strip().lower()
            raw_style = "llm"

        if not raw_name:
            continue

        for suffix in known_suffixes:
            if raw_name.endswith(suffix):
                raw_name = raw_name[: -len(suffix)]
                break

        normalized_name = raw_name.replace(" ", "")
        if not normalized_name or normalized_name in seen:
            continue
        seen.add(normalized_name)

        normalized_style = raw_style.replace("-", "_").replace(" ", "_") or "llm"
        suggestions.append({"name": normalized_name, "method": normalized_style})

    return suggestions


def llm_creative_boost(
    niche: str,
    existing: list[str],
    selected_keywords: list[str] | None = None,
    requested_styles: list[str] | None = None,
    geo_context: str = "",
    count: int = 8,
) -> list[dict[str, str]]:
    """Ask the configured LLM for extra domain ideas across the most relevant naming styles."""
    system, prompt = _build_domain_generation_prompt(
        niche=niche,
        existing=existing,
        selected_keywords=selected_keywords,
        requested_styles=requested_styles,
        geo_context=geo_context,
        count=count,
    )
    text = call_llm(prompt, system=system, json_mode=True)
    return _normalize_llm_domain_suggestions(parse_json_response(text, "domains"))


def preflight_generation_model() -> tuple[bool, str]:
    """Check whether the configured LLM path is usable before generation."""
    result = call_llm("Reply with the single word ready.")
    message = st.session_state.get("last_llm_message", "")
    if result:
        return True, message or "سيتم استخدام الذكاء الاصطناعي أثناء التوليد."
    return False, message or f"تعذر استخدام الذكاء الاصطناعي. {OFFLINE_ENGINE_MESSAGE}"


def ai_suggest_words(niche: str, category: str, current_words: list[str]) -> list[str]:
    """Ask the configured LLM for extra word-bank suggestions."""
    prompt = (
        f"Suggest 10 new high-quality, brandable single-word domain concepts for the category '{category}' "
        f"in the '{niche}' niche. Return ONLY absolute single words, max 15 chars each. "
        f"Return ONLY a JSON object: {{\"words\": [\"word1\", \"word2\", ...]}}"
    )
    system = "You are a professional domain name brand expert."
    text = call_llm(prompt, system=system, json_mode=True)
    raw_words = parse_json_response(text, "words")
    return [
        word.replace(" ", "").lower().strip()
        for word in raw_words
        if word and len(word.replace(" ", "")) <= 20 and word not in current_words
    ]


def ai_suggest_keywords_from_topic(
    topic: str,
    niches: list[str],
    profiles: list[str],
    existing_keywords: list[str] | None = None,
    count: int = 10,
) -> list[str]:
    """Suggest short domain-generation keywords from a user topic plus current context."""
    existing = [keyword.strip().lower() for keyword in (existing_keywords or []) if keyword.strip()]
    niche_context = ", ".join(niches) if niches else "general"
    profile_context = ", ".join(profiles) if profiles else "startup_brand"
    prompt = (
        f"The user wants domain ideas around this topic: '{topic}'. "
        f"Selected niches: {niche_context}. "
        f"Selected scoring profiles: {profile_context}. "
        "Apply the investor-style filtering and naming analysis framework before proposing anything. "
        f"Then output only the strongest {count} short, commercially useful keyword seeds for domain generation. "
        "Focus on reusable market language, buyer logic, product naming relevance, and words that combine well into serious brandable domains. "
        "Reject weak, hype-only, trademark-heavy, awkward, or low-resale terminology. "
        f"Avoid duplicates and avoid these existing keywords: {existing[:20]}. "
        "Return only concise seed keywords, not full domains and not a report. "
        f"Return ONLY a JSON object: {{\"keywords\": [\"word1\", \"word2\", ...]}}"
    )
    system = (
        f"{TOPIC_KEYWORD_SYSTEM_PROMPT}\n\n"
        "For this task, you are being used as a keyword-selection engine inside an app sidebar.\n"
        "Do the full internal analysis, but DO NOT output the full framework sections.\n"
        "Your visible output must be JSON only, with a single top-level key named 'keywords'.\n"
        "Each keyword must be lowercase, short, commercially relevant, easy to combine into domains, and safe to reuse.\n"
        "Prefer 1-word seeds. Use 2 words only if the phrase is unusually strong and commercially standard."
    )
    text = call_llm(prompt, system=system, json_mode=True)
    raw_keywords = parse_json_response(text, "keywords")
    return [
        keyword.replace(" ", "").lower().strip()
        for keyword in raw_keywords
        if keyword and 2 <= len(keyword.replace(" ", "")) <= 20 and keyword.replace(" ", "").lower().strip() not in existing
    ]


def ai_refine_shortlist_domains(
    shortlist_rows: list[dict[str, object]],
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    """Use the configured LLM to refine only the strongest shortlist candidates."""
    if not shortlist_rows:
        return []

    trimmed_rows = shortlist_rows[: max(1, min(limit, 10))]
    compact_rows: list[dict[str, object]] = []
    for row in trimmed_rows:
        compact_rows.append(
            {
                "domain": str(row.get("Domain") or ""),
                "theme": str(row.get("Theme") or ""),
                "keyword": str(row.get("Keyword") or ""),
                "niche": str(row.get("Niche") or ""),
                "buyer_type": str(row.get("Buyer Type") or ""),
                "score": row.get("Score") or "",
                "grade": str(row.get("Grade") or ""),
                "profile": str(row.get("Profile") or ""),
                "style": str(row.get("Style") or ""),
                "rationale": str(row.get("Rationale") or ""),
                "risk_notes": str(row.get("Risk Notes") or ""),
            }
        )

    prompt = (
        "Review this shortlisted domain set and refine it like a strict investor. "
        "Do not generate new names. Only evaluate the provided shortlist. "
        f"Return at most {len(compact_rows)} reviewed rows.\n\n"
        f"Shortlist JSON:\n{json.dumps(compact_rows, ensure_ascii=True)}"
    )
    text = call_llm(prompt, system=SHORTLIST_REFINEMENT_SYSTEM_PROMPT, json_mode=True)
    raw_items = parse_json_response(text, "refined_domains")

    normalized_items: list[dict[str, object]] = []
    seen_domains: set[str] = set()
    valid_domains = {str(row.get("Domain") or "") for row in trimmed_rows}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip()
        if not domain or domain not in valid_domains or domain in seen_domains:
            continue
        seen_domains.add(domain)

        try:
            investor_score = float(item.get("investor_score") or 0)
        except (TypeError, ValueError):
            investor_score = 0.0

        verdict = str(item.get("verdict") or "hold_watch").strip().lower()
        if verdict not in {"buy_now", "hold_watch", "reject"}:
            verdict = "hold_watch"

        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in {"high", "medium", "low"}:
            priority = "medium"

        normalized_items.append(
            {
                "domain": domain,
                "investor_score": _normalize_bounded_score(investor_score),
                "verdict": verdict,
                "priority": priority,
                "buyer_angle": str(item.get("buyer_angle") or "").strip(),
                "why_good": str(item.get("why_good") or "").strip(),
                "risk_summary": str(item.get("risk_summary") or "").strip(),
            }
        )
    return normalized_items


def ai_refine_themes(
    theme_rows: list[dict[str, object]],
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    """Use the configured LLM to review only the current visible theme slice."""
    if not theme_rows:
        return []

    trimmed_rows = theme_rows[: max(1, min(limit, 10))]
    compact_rows: list[dict[str, object]] = []
    for row in trimmed_rows:
        compact_rows.append(
            {
                "theme": str(row.get("Theme") or ""),
                "classification": str(row.get("Classification") or ""),
                "momentum": row.get("Momentum") or "",
                "signals": row.get("Signals") or "",
                "source_types": str(row.get("Source Types") or ""),
                "source_tags": str(row.get("Source Tags") or ""),
                "source_entities": str(row.get("Source Entities") or ""),
                "related_terms": str(row.get("Related Terms") or ""),
                "description": str(row.get("Description") or ""),
            }
        )

    prompt = (
        "Review this visible theme slice like a strict investor-facing trend analyst. "
        "Do not create new themes. Only evaluate the provided theme rows. "
        f"Return at most {len(compact_rows)} reviewed rows.\n\n"
        f"Theme JSON:\n{json.dumps(compact_rows, ensure_ascii=True)}"
    )
    text = call_llm(prompt, system=THEME_REFINEMENT_SYSTEM_PROMPT, json_mode=True)
    raw_items = parse_json_response(text, "refined_themes")

    normalized_items: list[dict[str, object]] = []
    seen_themes: set[str] = set()
    valid_themes = {str(row.get("Theme") or "") for row in trimmed_rows}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        theme = str(item.get("theme") or "").strip()
        if not theme or theme not in valid_themes or theme in seen_themes:
            continue
        seen_themes.add(theme)

        action = str(item.get("action") or "watch").strip().lower()
        if action not in {"promote", "watch", "drop"}:
            action = "watch"

        normalized_items.append(
            {
                "theme": theme,
                "confidence": _normalize_bounded_score(item.get("confidence")),
                "action": action,
                "suggested_niche": str(item.get("suggested_niche") or "").strip(),
                "buyer_angle": str(item.get("buyer_angle") or "").strip(),
                "domain_direction": str(item.get("domain_direction") or "").strip(),
                "why_now": str(item.get("why_now") or "").strip(),
                "risk_summary": str(item.get("risk_summary") or "").strip(),
            }
        )
    return normalized_items


def ai_refine_keywords(
    keyword_rows: list[dict[str, object]],
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Use the configured LLM to review only the current visible keyword slice."""
    if not keyword_rows:
        return []

    trimmed_rows = keyword_rows[: max(1, min(limit, 12))]
    compact_rows: list[dict[str, object]] = []
    for row in trimmed_rows:
        compact_rows.append(
            {
                "keyword": str(row.get("Keyword") or ""),
                "type": str(row.get("Type") or ""),
                "theme": str(row.get("Theme") or ""),
                "niche": str(row.get("Niche") or ""),
                "buyer_type": str(row.get("Buyer Type") or ""),
                "commercial": row.get("Commercial") or "",
                "novelty": row.get("Novelty") or "",
                "brandability": row.get("Brandability") or "",
                "notes": str(row.get("Notes") or ""),
            }
        )

    prompt = (
        "Review this visible keyword-intelligence slice like a strict investor-facing naming analyst. "
        "Do not create new keywords. Only evaluate the provided keyword rows. "
        f"Return at most {len(compact_rows)} reviewed rows.\n\n"
        f"Keyword JSON:\n{json.dumps(compact_rows, ensure_ascii=True)}"
    )
    text = call_llm(prompt, system=KEYWORD_REFINEMENT_SYSTEM_PROMPT, json_mode=True)
    raw_items = parse_json_response(text, "refined_keywords")

    normalized_items: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, str]] = set()
    valid_pairs = {
        (str(row.get("Keyword") or ""), str(row.get("Theme") or ""))
        for row in trimmed_rows
    }
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "").strip()
        theme = str(item.get("theme") or "").strip()
        key_pair = (keyword, theme)
        if not keyword or not theme or key_pair not in valid_pairs or key_pair in seen_pairs:
            continue
        seen_pairs.add(key_pair)

        action = str(item.get("action") or "keep").strip().lower()
        if action not in {"promote", "keep", "drop"}:
            action = "keep"

        normalized_items.append(
            {
                "keyword": keyword,
                "theme": theme,
                "confidence": _normalize_bounded_score(item.get("confidence")),
                "commercial_fit": _normalize_bounded_score(item.get("commercial_fit")),
                "naming_fit": _normalize_bounded_score(item.get("naming_fit")),
                "action": action,
                "suggested_keyword_type": str(item.get("suggested_keyword_type") or "").strip(),
                "suggested_niche": str(item.get("suggested_niche") or "").strip(),
                "buyer_angle": str(item.get("buyer_angle") or "").strip(),
                "why_good": str(item.get("why_good") or "").strip(),
                "risk_summary": str(item.get("risk_summary") or "").strip(),
            }
        )
    return normalized_items


def test_connection(provider_name: str, api_key: str, model: str) -> tuple[bool, str]:
    """Run a minimal provider test using the current app routing logic."""
    _ = api_key, model
    previous_provider = st.session_state.get("ai_provider")
    st.session_state["ai_provider"] = provider_name
    result = call_llm("ping", json_mode=False)
    st.session_state["ai_provider"] = previous_provider
    if result:
        return True, f"✅ تم الربط بـ {model} بنجاح!"
    return False, "❌ فشل الربط — تأكد من الـ API Key والموديل"
