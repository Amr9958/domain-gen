import streamlit as st
import random
import re
import pandas as pd
import json
from datetime import datetime
import whois
import sqlite3
import socket
from openai import OpenAI
from google import genai
import webbrowser
from urllib.parse import quote
import io
import os

st.set_page_config(page_title="DomainTrade Pro V5", page_icon="🔥", layout="wide")

# ==================== DB SETUP ====================

def init_db():
    conn = sqlite3.connect("domains.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY,
        full_domain TEXT UNIQUE,
        name TEXT,
        ext TEXT,
        niche TEXT,
        appraisal_tier TEXT,
        appraisal_value TEXT,
        score INTEGER,
        status TEXT,
        generated_date TEXT,
        purchased_date TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def add_to_portfolio(full_domain, name, ext, niche, appraisal_tier, appraisal_value, score=0):
    conn = sqlite3.connect("domains.db")
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO domains
            (full_domain, name, ext, niche, appraisal_tier, appraisal_value, score, status, generated_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (full_domain, name, ext, niche, appraisal_tier, appraisal_value, score, "Available",
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        st.success(f"✅ {full_domain} تمت إضافته للـ Portfolio")
    except:
        st.info("الدومين موجود بالفعل")
    conn.close()

def get_portfolio():
    conn = sqlite3.connect("domains.db")
    df = pd.read_sql_query("SELECT * FROM domains ORDER BY score DESC, generated_date DESC", conn)
    conn.close()
    return df

# ==================== PRONOUNCEABILITY & SCORING ====================

def is_pronounceable(name: str) -> bool:
    """
    Improved check: allows common consonant clusters (str, spr, thr, etc.)
    Rejects 4+ consecutive consonants and triple repeated chars.
    """
    name_lower = name.lower()
    # Allow known clusters before checking
    cleaned = re.sub(r'(str|spr|thr|chr|ph|sh|th|ch|wh|ck|qu|ng|gh)', 'X', name_lower)
    if re.search(r'[bcdfghjklmnpqrstvwxyz]{4,}', cleaned):
        return False
    if re.search(r'(.)\1{2,}', name_lower):
        return False
    return True

def score_domain(name: str, niche: str = "") -> int:
    """
    Comprehensive domain scoring (0-100):
    - Length (ideal 5-10 chars)
    - Pronounceability
    - No hyphens/numbers
    - Niche relevance
    - Starts with a letter
    - Not ending in awkward suffix
    """
    score = 0
    length = len(name)

    # Length scoring (most valuable range: 5-9 chars)
    if 5 <= length <= 7:
        score += 35
    elif 8 <= length <= 10:
        score += 25
    elif length <= 12:
        score += 15
    elif length <= 15:
        score += 5

    # Pronounceability
    if is_pronounceable(name):
        score += 20

    # No hyphens or numbers (cleaner brand)
    if not re.search(r'[-_\d]', name):
        score += 10

    # Starts with a letter
    if name[0].isalpha():
        score += 5

    # Niche relevance: check if any niche-related word bank word appears in name
    banks = st.session_state.get("word_banks", {})
    niche_map = {
        "Tech & AI": ["tech", "ai"],
        "Finance & SaaS": ["finance", "abstract"],
        "E-commerce": ["power", "abstract"],
        "Creative & Arts": ["creative"],
        "Health & Wellness": ["abstract"],
        "Real Estate": ["power", "abstract"],
    }
    relevant_cats = niche_map.get(niche, list(banks.keys()))
    for cat in relevant_cats:
        for word in banks.get(cat, []):
            if word in name.lower() and len(word) >= 3:
                score += 15
                break

    # Bonus: short_prefix boost (high-value prefix like "ai", "io", "neo")
    high_value_prefixes = ["ai", "io", "neo", "evo", "zap", "vox", "rx", "ex"]
    for pfx in high_value_prefixes:
        if name.lower().startswith(pfx) or name.lower().endswith(pfx):
            score += 10
            break

    return min(score, 100)

def appraise_name(name: str, niche: str = "") -> dict:
    score = score_domain(name, niche)
    if score >= 70:
        return {"tier": "🔥 Premium", "value": "$2,500 - $8,000", "score": score}
    elif score >= 45:
        return {"tier": "⚖️ Mid", "value": "$800 - $2,500", "score": score}
    else:
        return {"tier": "🧪 Experimental", "value": "$200 - $800", "score": score}

# ==================== AVAILABILITY CHECK ====================

def check_availability(domain_with_ext: str):
    try:
        w = whois.whois(domain_with_ext)
        return "🟢 Available" if not w.creation_date else "🔴 Taken"
    except:
        try:
            socket.gethostbyname(domain_with_ext.split('.')[0] + ".com")
            return "🔴 Taken"
        except:
            return "🟢 Available"

# ==================== UNIFIED AI CALLER ====================

def call_llm(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """
    Unified LLM caller — handles xAI, Gemini, OpenRouter.
    Returns raw string response.
    """
    provider = st.session_state.get("ai_provider", "xAI (Grok)")

    if provider == "xAI (Grok)":
        xai_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
        xai_model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-3-mini")).strip()
        if not xai_key:
            return ""
        try:
            client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            kwargs = {"messages": messages, "model": xai_model, "max_tokens": 500}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content
        except Exception as e:
            st.sidebar.error(f"xAI Error: {e}")
            return ""

    elif provider == "Google Gemini":
        gemini_key = st.secrets.get("GEMINI_API_KEY", st.session_state.get("gemini_key", "")).strip()
        gemini_model = st.secrets.get("GEMINI_MODEL", st.session_state.get("gemini_model", "gemini-2.0-flash")).strip()
        if not gemini_key:
            return ""
        try:
            client = genai.Client(api_key=gemini_key)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = client.models.generate_content(model=gemini_model, contents=full_prompt)
            return response.text.strip()
        except Exception as e:
            st.sidebar.error(f"Gemini Error: {e}")
            return ""

    elif provider == "OpenRouter":
        or_key = st.secrets.get("OPENROUTER_API_KEY", st.session_state.get("or_key", "")).strip()
        or_model = st.secrets.get("OPENROUTER_MODEL", st.session_state.get("or_model", "google/gemini-2.0-flash-001")).strip()
        if not or_key:
            return ""
        try:
            client = OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(messages=messages, model=or_model, max_tokens=500)
            return resp.choices[0].message.content.strip()
        except Exception as e:
            st.sidebar.error(f"OpenRouter Error: {e}")
            return ""

    return ""

def parse_json_response(text: str, key: str) -> list:
    """Safely parse JSON from LLM response, handles markdown fences."""
    if not text:
        return []
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        return data.get(key, list(data.values())[0] if data else [])
    except:
        return []

def llm_creative_boost(niche: str, existing: list, count=8) -> list:
    prompt = (f"Generate {count} unique, brandable, 1-word or 2-word domain names for the '{niche}' niche. "
              f"Avoid: {existing[:20]}. Focus on short (5-12 chars), memorable names. "
              f"Return ONLY a JSON object: {{\"domains\": [\"name1\", \"name2\", ...]}}")
    text = call_llm(prompt, json_mode=True)
    return [n.lower().replace(" ", "") for n in parse_json_response(text, "domains")]

def ai_suggest_words(niche: str, category: str, current_words: list) -> list:
    prompt = (f"Suggest 10 new high-quality, brandable single-word domain concepts for the category '{category}' "
              f"in the '{niche}' niche. Return ONLY absolute single words, max 15 chars each. "
              f"Return ONLY a JSON object: {{\"words\": [\"word1\", \"word2\", ...]}}")
    system = "You are a professional domain name brand expert."
    text = call_llm(prompt, system=system, json_mode=True)
    raw = parse_json_response(text, "words")
    return [w.replace(" ", "").lower().strip() for w in raw if w and len(w.replace(" ", "")) <= 20]

# ==================== CONNECTION TESTERS ====================

def test_connection(provider_name: str, api_key: str, model: str) -> tuple:
    prev = st.session_state.get("ai_provider")
    st.session_state["ai_provider"] = provider_name
    result = call_llm("ping", json_mode=False)
    st.session_state["ai_provider"] = prev
    if result:
        return True, f"✅ تم الربط بـ {model} بنجاح!"
    return False, f"❌ فشل الربط — تأكد من الـ API Key والموديل"

# ==================== DOMAIN GENERATION ====================

def generate_domains(niche: str, use_llm: bool, keywords_str: str = "", num_per_tier: int = 15) -> list:
    banks = st.session_state.word_banks
    user_keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]
    base_names = set()

    # Smart combinatorial generation
    loop_count = num_per_tier * 8
    all_cats = list(banks.keys())

    for _ in range(loop_count):
        cat = random.choice(all_cats)
        word1 = random.choice(banks[cat])

        r = random.random()
        if user_keywords and r > 0.3:
            kw = random.choice(user_keywords)
            name = (kw + word1) if random.random() > 0.5 else (word1 + kw)
        elif r > 0.6:
            # short prefix + word combo
            prefix_words = banks.get("short_prefixes", [])
            if prefix_words:
                pfx = random.choice(prefix_words)
                name = pfx + word1
            else:
                cat2 = random.choice(all_cats)
                word2 = random.choice(banks[cat2])
                name = word1 + word2
        else:
            cat2 = random.choice(all_cats)
            word2 = random.choice(banks[cat2])
            name = word1 + word2

        # Filter: max 18 chars, letters only
        name = re.sub(r'[^a-z]', '', name.lower())
        if 4 <= len(name) <= 18:
            base_names.add(name)

    # LLM boost
    if use_llm:
        llm_names = llm_creative_boost(niche, list(base_names), count=num_per_tier)
        for n in llm_names:
            clean = re.sub(r'[^a-z]', '', n.lower())
            if 4 <= len(clean) <= 18:
                base_names.add(clean)

    return list(base_names)

# ==================== WORD BANK PERSISTENCE ====================

def load_word_banks():
    base_path = "word_banks"
    defaults = {
        "abstract": ["nexus", "quantum", "vertex", "prime", "zenith", "arc", "flux", "core", "omni", "nova",
                     "cipher", "echo", "orbit", "axiom", "rune", "lumen", "ether", "apex", "aeon", "epoch"],
        "power": ["boost", "pro", "master", "elite", "ultra", "max", "hyper", "mega", "titan", "force",
                  "surge", "drive", "grand", "super", "grip", "iron", "steel", "bold", "hero", "epic",
                  "citadel", "vanguard", "forge", "kinetic", "ascend"],
        "tech": ["logic", "code", "dev", "sys", "net", "cloud", "ai", "stack", "bit", "data",
                 "cyber", "tide", "link", "node", "sync", "byte", "bot", "hub", "web", "mesh",
                 "deploy", "auth", "relay", "edge", "kern", "trace", "infra", "cache", "gpu", "api"],
        "finance": ["pay", "coin", "fund", "equity", "trust", "cap", "wealth", "asset", "fin", "cash",
                    "credit", "vault", "trade", "hedge", "bond", "gold", "mint", "gain", "risk", "deal",
                    "ledger", "quant", "yield", "pivot", "folio", "accord", "fiscal", "sterling", "rally", "merit"],
        "creative": ["spark", "mind", "vision", "art", "pixel", "canvas", "design", "studio", "craft", "muse",
                     "brush", "ink", "hue", "tone", "shade", "draw", "build", "fuse", "lumina", "dawn",
                     "palette", "glyph", "mosaic", "vivid", "atelier", "motif", "render", "quill", "neon", "prism"],
        "short_prefixes": ["my", "go", "up", "now", "pro", "try", "use", "top", "one", "new",
                           "max", "fly", "run", "zen", "pure", "true", "real", "wide", "open", "wise",
                           "bold", "calm", "cool", "clear", "fast", "smart", "ai", "io", "neo", "evo",
                           "zap", "vox", "rex", "duo", "arc", "hex", "jet", "leo", "ori", "rx"]
    }

    if not os.path.exists(base_path):
        os.makedirs(base_path)

    banks = {}
    for cat, default_words in defaults.items():
        file_path = os.path.join(base_path, f"{cat}.txt")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                words = [w.strip().lower() for w in content.replace("\n", ",").split(",") if w.strip()]
                banks[cat] = list(dict.fromkeys(words))  # deduplicate preserving order
            else:
                banks[cat] = default_words
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(", ".join(default_words))
            banks[cat] = default_words

    return banks

def save_word_banks(banks):
    base_path = "word_banks"
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    for cat, words in banks.items():
        # Deduplicate before saving
        unique_words = list(dict.fromkeys(words))
        file_path = os.path.join(base_path, f"{cat}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(", ".join(unique_words))

# ==================== SESSION STATE ====================

if "word_banks" not in st.session_state:
    st.session_state.word_banks = load_word_banks()
if "history" not in st.session_state:
    st.session_state.history = []
if "favorites" not in st.session_state:
    st.session_state.favorites = []

# ==================== SIDEBAR ====================

if st.sidebar.button("🗑️ Reset All App Data", type="secondary"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.divider()
st.sidebar.title("🔧 DomainTrade Pro V5")
st.sidebar.caption("Smarter Scoring · Unified AI · Clean Code")

with st.sidebar.expander("🔑 AI Settings & Keys", expanded=True):
    st.session_state.ai_provider = st.selectbox(
        "AI Provider", ["xAI (Grok)", "Google Gemini", "OpenRouter"],
        index=["xAI (Grok)", "Google Gemini", "OpenRouter"].index(
            st.session_state.get("ai_provider", "xAI (Grok)"))
    )
    st.divider()

    if st.session_state.ai_provider == "xAI (Grok)":
        xai_key_input = st.text_input("Grok (xAI) API Key",
            value=st.session_state.get("xai_key", st.secrets.get("XAI_API_KEY", "")),
            type="password")
        st.session_state.xai_key = xai_key_input
        xai_model_input = st.text_input("Model Name",
            value=st.session_state.get("xai_model", st.secrets.get("XAI_MODEL", "grok-3-mini")))
        st.session_state.xai_model = xai_model_input
        if st.button("🔌 Test xAI"):
            ok, msg = test_connection("xAI (Grok)", st.session_state.xai_key, st.session_state.xai_model)
            (st.sidebar.success if ok else st.sidebar.error)(msg)

    elif st.session_state.ai_provider == "Google Gemini":
        gemini_key_input = st.text_input("Gemini API Key",
            value=st.session_state.get("gemini_key", st.secrets.get("GEMINI_API_KEY", "")),
            type="password")
        st.session_state.gemini_key = gemini_key_input
        gemini_model_input = st.text_input("Model Name",
            value=st.session_state.get("gemini_model", st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash")))
        st.session_state.gemini_model = gemini_model_input
        if st.button("🔌 Test Gemini"):
            ok, msg = test_connection("Google Gemini", st.session_state.gemini_key, st.session_state.gemini_model)
            (st.sidebar.success if ok else st.sidebar.error)(msg)

    else:
        or_key_input = st.text_input("OpenRouter API Key",
            value=st.session_state.get("or_key", st.secrets.get("OPENROUTER_API_KEY", "")),
            type="password")
        st.session_state.or_key = or_key_input
        or_model_input = st.text_input("Model Name",
            value=st.session_state.get("or_model", st.secrets.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")))
        st.session_state.or_model = or_model_input
        if st.button("🔌 Test OpenRouter"):
            ok, msg = test_connection("OpenRouter", st.session_state.or_key, st.session_state.or_model)
            (st.sidebar.success if ok else st.sidebar.error)(msg)

    st.divider()
    st.session_state.nc_api_user = st.text_input("Namecheap ApiUser", type="password")
    st.session_state.nc_api_key = st.text_input("Namecheap ApiKey", type="password")
    st.session_state.nc_username = st.text_input("Namecheap Username", type="password")

niche = st.sidebar.selectbox("Niche", ["Tech & AI", "Finance & SaaS", "E-commerce", "Creative & Arts", "Health & Wellness", "Real Estate"])
keywords = st.sidebar.text_input("🎯 Keywords (comma separated)", placeholder="e.g. fast, smart, secure")
num_per_tier = st.sidebar.slider("Domains per Tier", 5, 50, 15)
extensions = st.sidebar.multiselect("الامتدادات", [".com", ".net", ".org", ".io", ".ai", ".co", ".app", ".dev"], default=[".com", ".ai"])
use_llm = st.sidebar.checkbox("LLM Creative Boost", value=True)
use_availability = st.sidebar.checkbox("Auto Availability Check", value=True)

# ==================== TABS ====================

tab1, tab2, tab_fav, tab3, tab4, tab5 = st.tabs([
    "🚀 Generator", "📚 Word Banks", "⭐ Favorites", "📊 History", "📦 My Portfolio", "📈 Stats"
])

# ==================== TAB 1: GENERATOR ====================

with tab1:
    st.title("🔥 DomainTrade Pro V5 — Smart Scoring")

    if st.button("🚀 Generate Domains", type="primary"):
        st.session_state.generating = True
        st.session_state.last_results = []
        st.session_state.show_results = False
        st.rerun()

    if st.session_state.get("generating", False):
        with st.spinner("جاري التوليد والتقييم الذكي..."):
            names = generate_domains(niche, use_llm, keywords, num_per_tier)
            categories = {"🔥 Premium": [], "⚖️ Mid": [], "🧪 Experimental": []}
            for name in names:
                appr = appraise_name(name, niche)
                categories[appr["tier"]].append((name, appr))
            # Sort each tier by score descending
            for tier in categories:
                categories[tier].sort(key=lambda x: x[1]["score"], reverse=True)
            st.session_state.last_categories = categories
            st.session_state.generating = False
            st.session_state.show_results = True
            for tier, items in categories.items():
                for name, appraisal in items:
                    st.session_state.history.append({
                        "Name": name, "Tier": tier, "Score": appraisal["score"],
                        "Value": appraisal["value"], "Niche": niche,
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
        st.rerun()

    if st.session_state.get("show_results", False):
        categories = st.session_state.get("last_categories", {})
        all_generated_full = []

        for tier, items in categories.items():
            items_sliced = items[:num_per_tier]
            if not items_sliced:
                continue
            st.subheader(f"{tier} Domains")
            for name, appraisal in items_sliced:
                for ext in extensions:
                    full = f"{name}{ext}"
                    all_generated_full.append(full)
                    status = check_availability(full) if use_availability else ""
                    col1, col2, col3, col4 = st.columns([3, 1, 2, 2])
                    with col1:
                        color = "green" if "Available" in status else ("red" if "Taken" in status else "gray")
                        st.markdown(f"**:{color}[{full}]**" if status else f"**{full}**")
                    with col2:
                        st.caption(f"⭐ {appraisal['score']}/100")
                    with col3:
                        st.caption(f"{appraisal['value']} {status}")
                    with col4:
                        c1, c2, c3 = st.columns(3)
                        if "Available" in status:
                            with c1:
                                if st.button("🛒", key=f"buy_{full}", help="Buy on Namecheap"):
                                    webbrowser.open(f"https://www.namecheap.com/domains/registration/results/?domain={quote(full)}")
                            with c2:
                                if st.button("➕", key=f"add_{full}", help="Add to Portfolio"):
                                    add_to_portfolio(full, name, ext, niche, appraisal["tier"], appraisal["value"], appraisal["score"])
                        with c3:
                            is_fav = full in [f['domain'] for f in st.session_state.favorites]
                            if st.button("💖" if is_fav else "🤍", key=f"fav_{full}"):
                                if not is_fav:
                                    st.session_state.favorites.append({
                                        "domain": full, "tier": appraisal["tier"],
                                        "score": appraisal["score"], "value": appraisal["value"], "niche": niche
                                    })
                                    st.toast(f"✅ تمت إضافة {full} للمفضلة")
                                else:
                                    st.session_state.favorites = [f for f in st.session_state.favorites if f['domain'] != full]
                                    st.toast(f"🗑️ تمت إزالة {full} من المفضلة")
                                st.rerun()

        if all_generated_full:
            st.session_state.last_results = all_generated_full
            st.divider()
            st.success(f"🎉 تم إيجاد {len(all_generated_full)} دومين.")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.text_area("📋 Copy All", value="\n".join(all_generated_full), height=120)
            with col_b:
                st.download_button("📥 Download TXT", data="\n".join(all_generated_full), file_name="domains_v5.txt")
            with col_c:
                if st.button("🧹 Clear Results"):
                    st.session_state.show_results = False
                    st.session_state.last_results = []
                    st.rerun()

# ==================== TAB 2: WORD BANKS ====================

with tab2:
    st.title("📚 Word Banks")

    col_s1, col_s2 = st.columns([1, 4])
    with col_s1:
        if st.button("💾 حفظ الكل", type="primary"):
            save_word_banks(st.session_state.word_banks)
            st.success("✅ تم حفظ جميع الكلمات في word_banks/")

    st.divider()
    uploaded_file = st.file_uploader("📥 استيراد بنك كلمات من ملف .txt", type="txt")
    if uploaded_file:
        content = uploaded_file.read().decode("utf-8")
        new_banks = {}
        for line in content.split("\n"):
            if ":" in line:
                cat, words = line.split(":", 1)
                new_banks[cat.strip()] = [w.strip().lower() for w in words.split(",") if w.strip()]
        if new_banks:
            st.session_state.word_banks = new_banks
            st.success("✅ تم استيراد بنك الكلمات بنجاح!")
            st.rerun()

    st.info("💡 نصيحة: استخدم ✨ AI Boost لإضافة كلمات إبداعية بناءً على الـ Niche المختار.")
    cols = st.columns(2)
    for i, (cat, words) in enumerate(st.session_state.word_banks.items()):
        with cols[i % 2]:
            st.divider()
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.subheader(f"📂 {cat}  ({len(words)} كلمة)")
            with c2:
                if st.button("✨ AI Boost", key=f"ai_btn_{cat}"):
                    with st.spinner("جاري التفكير..."):
                        suggestions = ai_suggest_words(niche, cat, words)
                        if suggestions:
                            new_list = list(dict.fromkeys(words + [s.lower() for s in suggestions]))
                            st.session_state.word_banks[cat] = new_list
                            st.session_state[f"area_{cat}"] = ", ".join(new_list)
                            st.success(f"✅ {len(suggestions)} كلمة جديدة!")
                            st.rerun()
                        else:
                            st.error("❌ تأكد من الـ API Key")
            with c3:
                if st.button("🗑️ مسح مكرر", key=f"dedup_{cat}"):
                    st.session_state.word_banks[cat] = list(dict.fromkeys(words))
                    st.rerun()

            new_words = st.text_area(
                f"كلمات قسم {cat}",
                value=", ".join(words),
                height=150,
                key=f"area_{cat}"
            )
            updated = [w.strip().lower() for w in new_words.split(",") if w.strip()]
            st.session_state.word_banks[cat] = list(dict.fromkeys(updated))

# ==================== TAB 3: FAVORITES ====================

with tab_fav:
    st.title("⭐ Favorites List")
    if st.session_state.favorites:
        fav_df = pd.DataFrame(st.session_state.favorites)
        st.dataframe(fav_df, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear All Favorites"):
                st.session_state.favorites = []
                st.rerun()
        with col2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                fav_df.to_excel(writer, index=False, sheet_name='Favorites')
            st.download_button("📥 Download Favorites (Excel)", data=output.getvalue(), file_name="favorites.xlsx")
    else:
        st.info("لم تقم بإضافة أي دومينات للمفضلة بعد.")

# ==================== TAB 4: HISTORY ====================

with tab3:
    st.title("📊 History (Current Session)")
    if st.session_state.history:
        df_hist = pd.DataFrame(st.session_state.history)
        # Show top scored first
        if "Score" in df_hist.columns:
            df_hist = df_hist.sort_values("Score", ascending=False)
        st.dataframe(df_hist, use_container_width=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_hist.to_excel(writer, index=False, sheet_name='History')
        st.download_button("📥 Download History (Excel)", data=output.getvalue(), file_name="domain_history.xlsx")
    else:
        st.info("لا يوجد سجل لهذه الجلسة بعد.")

# ==================== TAB 5: PORTFOLIO ====================

with tab4:
    st.title("📦 My Domains Portfolio")
    df = get_portfolio()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            domain_to_buy = st.selectbox("اختر دومين لشرائه", df['full_domain'])
            if st.button("🛒 Buy Now"):
                webbrowser.open(f"https://www.namecheap.com/domains/registration/results/?domain={quote(domain_to_buy)}")
        with col2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Portfolio')
            st.download_button("📥 Export Portfolio (Excel)", data=output.getvalue(), file_name="portfolio.xlsx")
    else:
        st.info("الـ Portfolio فاضي – ابدأ توليد وأضف دومينات!")

# ==================== TAB 6: STATS ====================

with tab5:
    st.title("📈 Portfolio Stats")
    df = get_portfolio()
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Domains", len(df))
        col2.metric("🔥 Premium", len(df[df['appraisal_tier'].str.contains("Premium", na=False)]))
        col3.metric("⚖️ Mid", len(df[df['appraisal_tier'].str.contains("Mid", na=False)]))
        col4.metric("Avg Score", f"{df['score'].mean():.0f}/100" if 'score' in df.columns else "N/A")
        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Niche Distribution")
            st.bar_chart(df['niche'].value_counts())
        with col_b:
            st.subheader("Tier Distribution")
            st.bar_chart(df['appraisal_tier'].value_counts())
    else:
        st.info("لا توجد بيانات للإحصائيات حالياً.")

st.divider()
st.caption("DomainTrade Pro V5 · Smarter Scoring · Unified AI Engine · Clean Code · Portfolio DB")