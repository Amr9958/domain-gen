"""LLM provider integrations used by the Streamlit app."""

from __future__ import annotations

import json

import streamlit as st
from google import genai
from openai import OpenAI

from constants import DEFAULT_AI_PROVIDER


XAI_PROVIDER = "xAI (Grok)"
GEMINI_PROVIDER = "Google Gemini"
OPENROUTER_PROVIDER = "OpenRouter"
OPENROUTER_FREE_MODEL = "openrouter/free"
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


def _set_llm_status(status: str, message: str, model_used: str = "") -> None:
    """Store the latest LLM routing/result status for the UI."""
    st.session_state["last_llm_status"] = status
    st.session_state["last_llm_message"] = message
    st.session_state["last_llm_model_used"] = model_used


def call_llm(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """Unified LLM caller for the currently selected provider."""
    provider = st.session_state.get("ai_provider", DEFAULT_AI_PROVIDER)

    if provider == XAI_PROVIDER:
        api_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
        model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-3-mini")).strip()
        if not api_key:
            _set_llm_status("disabled", "لا يوجد API Key صالح لـ xAI. سيتم الاعتماد على النظام الداخلي فقط.")
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
            _set_llm_status("internal_only", f"تعذر استخدام موديل xAI `{model}`. سيتم التوليد من خلال النظام الداخلي فقط.")
            st.sidebar.error(f"xAI Error: {exc}")
            return ""

    if provider == GEMINI_PROVIDER:
        api_key = st.secrets.get("GEMINI_API_KEY", st.session_state.get("gemini_key", "")).strip()
        model = st.secrets.get("GEMINI_MODEL", st.session_state.get("gemini_model", "gemini-2.0-flash")).strip()
        if not api_key:
            _set_llm_status("disabled", "لا يوجد API Key صالح لـ Gemini. سيتم الاعتماد على النظام الداخلي فقط.")
            return ""
        try:
            client = genai.Client(api_key=api_key)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = client.models.generate_content(model=model, contents=full_prompt)
            _set_llm_status("direct", f"سيتم استخدام Gemini بالموديل `{model}` أثناء التوليد.", model)
            return response.text.strip()
        except Exception as exc:
            _set_llm_status("internal_only", f"تعذر استخدام موديل Gemini `{model}`. سيتم التوليد من خلال النظام الداخلي فقط.")
            st.sidebar.error(f"Gemini Error: {exc}")
            return ""

    if provider == OPENROUTER_PROVIDER:
        api_key = st.secrets.get("OPENROUTER_API_KEY", st.session_state.get("or_key", "")).strip()
        model = st.secrets.get(
            "OPENROUTER_MODEL",
            st.session_state.get("or_model", "google/gemini-2.0-flash-001"),
        ).strip()
        if not api_key:
            _set_llm_status("disabled", "لا يوجد API Key صالح لـ OpenRouter. سيتم الاعتماد على النظام الداخلي فقط.")
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
                        f"تعذر استخدام OpenRouter بالموديل الأساسي والمجاني. سيتم التوليد من خلال النظام الداخلي فقط.",
                    )
                    st.sidebar.error(f"OpenRouter Error: {fallback_exc}")
                    return ""
            _set_llm_status(
                "internal_only",
                f"تعذر استخدام موديل OpenRouter `{model}`. سيتم التوليد من خلال النظام الداخلي فقط.",
            )
            st.sidebar.error(f"OpenRouter Error: {primary_exc}")
            return ""

    _set_llm_status("internal_only", "مزود الذكاء الاصطناعي غير معروف. سيتم التوليد من خلال النظام الداخلي فقط.")
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


def llm_creative_boost(
    niche: str,
    existing: list[str],
    selected_keywords: list[str] | None = None,
    count: int = 8,
) -> list[str]:
    """Ask the configured LLM for additional brandable domain ideas."""
    cleaned_keywords = [keyword.strip().lower() for keyword in (selected_keywords or []) if keyword.strip()]
    keyword_context = ", ".join(cleaned_keywords[:20])
    prompt = (
        f"Generate {count} unique, brandable domain names for the '{niche}' niche. "
        f"Selected keywords: {keyword_context or 'none provided'}. "
        "Stay tightly anchored to the selected keywords and direct commercial variations derived from them. "
        "Do not drift into unrelated naming territory. "
        f"Avoid: {existing[:20]}. Focus on short (5-14 chars), memorable names. "
        f"Return ONLY a JSON object: {{\"domains\": [\"name1\", \"name2\", ...]}}"
    )
    text = call_llm(prompt, json_mode=True)
    return [name.lower().replace(" ", "") for name in parse_json_response(text, "domains")]


def preflight_generation_model() -> tuple[bool, str]:
    """Check whether the configured LLM path is usable before generation."""
    result = call_llm("Reply with the single word ready.")
    message = st.session_state.get("last_llm_message", "")
    if result:
        return True, message or "سيتم استخدام الذكاء الاصطناعي أثناء التوليد."
    return False, message or "تعذر استخدام الذكاء الاصطناعي. سيتم التوليد من خلال النظام الداخلي فقط."


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
