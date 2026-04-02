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


st.set_page_config(page_title="DomainTrade Pro V4", page_icon="🔥", layout="wide")

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
        status TEXT,
        generated_date TEXT,
        purchased_date TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def add_to_portfolio(full_domain, name, ext, niche, appraisal_tier, appraisal_value):
    conn = sqlite3.connect("domains.db")
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO domains 
                    (full_domain, name, ext, niche, appraisal_tier, appraisal_value, status, generated_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (full_domain, name, ext, niche, appraisal_tier, appraisal_value, "Available", datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        st.success(f"✅ {full_domain} تمت إضافته للـ Portfolio")
    except:
        st.info("الدومين موجود بالفعل")
    conn.close()

def get_portfolio():
    conn = sqlite3.connect("domains.db")
    df = pd.read_sql_query("SELECT * FROM domains ORDER BY generated_date DESC", conn)
    conn.close()
    return df

# ==================== باقي الدوال (نفس V3 مع تحسين) ====================
def is_pronounceable(name: str) -> bool:
    name_lower = name.lower()
    if re.search(r'[bcdfghjklmnpqrstvwxyz]{3,}', name_lower) or re.search(r'(.)\1{2,}', name_lower):
        return False
    return True

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

def appraise_name(name: str) -> dict:
    score = 0
    length = len(name)
    if 6 <= length <= 9: score += 40
    elif length <= 12: score += 25
    if any(word in name.lower() for word in st.session_state.word_banks.get("abstract", [])): score += 30
    if any(word in name.lower() for word in st.session_state.word_banks.get("power", [])): score += 20
    if is_pronounceable(name): score += 10
    if score >= 70: return {"tier": "🔥 Premium", "value": "$2,500 - $8,000"}
    elif score >= 50: return {"tier": "⚖️ Mid", "value": "$800 - $2,500"}
    else: return {"tier": "🧪 Experimental", "value": "$200 - $800"}

def llm_creative_boost(niche: str, existing: list, count=8):
    provider = st.session_state.get("ai_provider", "xAI (Grok)")
    
    if provider == "xAI (Grok)":
        xai_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
        xai_model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-4.20-0309-reasoning")).strip()
        if not xai_key: return []
        try:
            client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
            prompt = f"Generate {count} unique, brandable, 1-word or 2-word domain names for the '{niche}' niche. Avoid: {existing}. Focus on short, memorable names. Return ONLY a JSON object: {{\"domains\": [\"name1\", \"name2\", ...]}}"
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=xai_model,
                response_format={"type": "json_object"}
            )
            data = json.loads(chat_completion.choices[0].message.content)
            return data.get("domains", list(data.values())[0])
        except Exception as e:
            st.sidebar.error(f"xAI Error: {e}")
            return []
    
    elif provider == "Google Gemini":
        gemini_key = st.secrets.get("GEMINI_API_KEY", st.session_state.get("gemini_key", "")).strip()
        gemini_model_name = st.secrets.get("GEMINI_MODEL", st.session_state.get("gemini_model", "gemini-2.0-flash")).strip()
        if not gemini_key: return []
        try:
            client = genai.Client(api_key=gemini_key)
            prompt = f"Generate {count} unique, brandable, 1-word or 2-word domain names for the '{niche}' niche. Avoid: {existing}. Return ONLY a JSON object: {{\"domains\": [\"name1\", \"name2\", ...]}}"
            response = client.models.generate_content(model=gemini_model_name, contents=prompt)
            text = response.text.strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
            data = json.loads(text)
            return data.get("domains", list(data.values())[0])
        except Exception as e:
            st.sidebar.error(f"Gemini Error: {e}")
            return []

    elif provider == "OpenRouter":
        or_key = st.secrets.get("OPENROUTER_API_KEY", st.session_state.get("or_key", "")).strip()
        or_model = st.secrets.get("OPENROUTER_MODEL", st.session_state.get("or_model", "google/gemini-2.0-flash-001")).strip()
        if not or_key: return []
        try:
            client = OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
            prompt = f"Generate {count} unique domain names for '{niche}'. Avoid: {existing}. Return ONLY a JSON object: {{\"domains\": [\"name1\", \"name2\", ...]}}"
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=or_model
            )
            text = chat_completion.choices[0].message.content.strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
            data = json.loads(text)
            return data.get("domains", list(data.values())[0])
        except Exception as e:
            st.sidebar.error(f"OpenRouter Error: {e}")
            return []
    return []

def generate_domains(niche, use_llm, keywords_str="", num_per_tier=15):
    base_names = []
    banks = st.session_state.word_banks
    user_keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]
    
    # 1. Combinatorial Generation (Higher count to fill tiers)
    # We aim for roughly 3 * num_per_tier total unique names
    loop_count = num_per_tier * 6
    for _ in range(loop_count):
        cat = random.choice(list(banks.keys()))
        word1 = random.choice(banks[cat])
        
        if user_keywords and random.random() > 0.3:
            kw = random.choice(user_keywords)
            name = kw + word1 if random.random() > 0.5 else word1 + kw
        else:
            cat2 = random.choice(list(banks.keys()))
            word2 = random.choice(banks[cat2])
            name = word1 + word2
            
        base_names.append(name.lower())

    if use_llm:
        llm_names = llm_creative_boost(niche, base_names, count=num_per_tier)
        base_names.extend([n.lower() for n in llm_names])
    
    return list(set(base_names))

# ==================== WORD BANK PERSISTENCE ====================
def load_word_banks():
    base_path = "word_banks"
    defaults = {
        "abstract": ["nexus", "quantum", "vertex", "prime", "zenith", "arc", "flux", "core", "omni", "nova"],
        "power": ["boost", "pro", "master", "elite", "ultra", "max", "hyper", "mega", "titan", "force"],
        "tech": ["logic", "code", "dev", "sys", "net", "cloud", "ai", "stack", "bit", "data"],
        "finance": ["pay", "coin", "fund", "equity", "trust", "cap", "wealth", "asset", "bank", "lend"],
        "creative": ["spark", "flow", "mind", "idea", "vision", "art", "pixel", "canvas", "design", "studio"],
        "short_prefixes": ["get", "my", "the", "re", "go", "on", "up", "in", "it", "be"]
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
                    # Support both comma-separated and newline-separated
                    if "," in content:
                        words = [w.strip().lower() for w in content.split(",") if w.strip()]
                    else:
                        words = [w.strip().lower() for w in content.split("\n") if w.strip()]
                    banks[cat] = words
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
        file_path = os.path.join(base_path, f"{cat}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(", ".join(words))

# ==================== SESSION STATE & SIDEBAR ====================
if "word_banks" not in st.session_state:
    st.session_state.word_banks = load_word_banks()


if "history" not in st.session_state:
    st.session_state.history = []

if "favorites" not in st.session_state:
    st.session_state.favorites = []

def test_xai_connection(api_key, model):
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        client.chat.completions.create(
            messages=[{"role": "user", "content": "ping"}],
            model=model,
            max_tokens=5
        )
        return True, f"✅ تم الربط بـ {model} بنجاح!"
    except Exception as e:
        return False, f"❌ فشل الربط: {e}"

def test_openrouter_connection(api_key, model_name):
    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        client.chat.completions.create(
            messages=[{"role": "user", "content": "ping"}],
            model=model_name,
            max_tokens=5
        )
        return True, f"✅ تم الربط بـ {model_name} (OpenRouter) بنجاح!"
    except Exception as e:
        return False, f"❌ فشل الربط: {e}"

def ai_suggest_words(niche, category, current_words):
    provider = st.session_state.get("ai_provider", "xAI (Grok)")
    prompt = (f"Suggest 10 new high-quality, professional, and brandable single-word domain concepts for the category '{category}' in the '{niche}' niche. "
              "Important: Return ONLY absolute single words! Do NOT combine words (e.g., return 'cloud' or 'smart', NOT 'smartcloud'). "
              "Focus on premium, modern, and catchy single English terms. Max length 15 characters."
              "Return ONLY a JSON object: {\"words\": [\"word1\", \"word2\", ...]}")
    
    raw_words = []
    if provider == "xAI (Grok)":
        xai_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
        xai_model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-4.20-0309-reasoning")).strip()
        if not xai_key: return []
        try:
            client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
            chat_completion = client.chat.completions.create(
                messages=[{"role": "system", "content": "You are a professional domain name brand expert."}, {"role": "user", "content": prompt}],
                model=xai_model,
                response_format={"type": "json_object"}
            )
            data = json.loads(chat_completion.choices[0].message.content)
            raw_words = data.get("words", list(data.values())[0])
        except Exception as e:
            st.sidebar.error(f"xAI Error: {e}")
            
    elif provider == "Google Gemini":
        gemini_key = st.secrets.get("GEMINI_API_KEY", st.session_state.get("gemini_key", "")).strip()
        gemini_model_name = st.secrets.get("GEMINI_MODEL", st.session_state.get("gemini_model", "gemini-2.0-flash")).strip()
        if not gemini_key: return []
        try:
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model=gemini_model_name, contents=prompt)
            text = response.text.strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
            data = json.loads(text)
            raw_words = data.get("words", list(data.values())[0])
        except Exception as e:
            st.sidebar.error(f"Gemini Error: {e}")

    elif provider == "OpenRouter":
        or_key = st.secrets.get("OPENROUTER_API_KEY", st.session_state.get("or_key", "")).strip()
        or_model = st.secrets.get("OPENROUTER_MODEL", st.session_state.get("or_model", "google/gemini-2.0-flash-001")).strip()
        if not or_key: return []
        try:
            client = OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=or_model
            )
            text = chat_completion.choices[0].message.content.strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
            data = json.loads(text)
            raw_words = data.get("words", list(data.values())[0])
        except Exception as e:
            st.sidebar.error(f"OpenRouter Error: {e}")

    # Post-processing: Remove spaces, limit length, enforce lowercase
    processed_words = []
    for w in raw_words:
        clean_w = w.replace(" ", "").lower().strip()
        if clean_w and len(clean_w) <= 20:
            processed_words.append(clean_w)
            
    return processed_words


# ==================== GLOBAL RESET ====================
if st.sidebar.button("🗑️ Reset All App Data", type="secondary"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.divider()
st.sidebar.title("🔧 DomainTrade Pro V4")
st.sidebar.caption("SaaS Ready – Portfolio + Auto Buy")

with st.sidebar.expander("🔑 AI Settings & Keys", expanded=True):
    # AI Provider Selector
    st.session_state.ai_provider = st.selectbox("AI Provider", ["xAI (Grok)", "Google Gemini", "OpenRouter"], 
                                               index=0 if st.session_state.get("ai_provider") == "xAI (Grok)" else (1 if st.session_state.get("ai_provider") == "Google Gemini" else 2))
    
    st.divider()
    
    if st.session_state.ai_provider == "xAI (Grok)":
        has_xai_secret = "XAI_API_KEY" in st.secrets
        xai_key_input = st.text_input("Grok (xAI) API Key", 
                                     value=st.session_state.get("xai_key", st.secrets.get("XAI_API_KEY", "grokApiKey-asa")), 
                                     type="password")
        st.session_state.xai_key = xai_key_input
        xai_model_input = st.text_input("Model Name", 
                                        value=st.session_state.get("xai_model", st.secrets.get("XAI_MODEL", "grok-4.20-0309-reasoning")))
        st.session_state.xai_model = xai_model_input
        
        if st.button("🔌 Test xAI"):
            success, msg = test_xai_connection(st.session_state.xai_key.strip(), st.session_state.xai_model.strip())
            if success: st.sidebar.success(msg)
            else: st.sidebar.error(msg)
            
    elif st.session_state.ai_provider == "Google Gemini":
        has_gemini_secret = "GEMINI_API_KEY" in st.secrets
        gemini_key_input = st.text_input("Gemini API Key", 
                                        value=st.session_state.get("gemini_key", st.secrets.get("GEMINI_API_KEY", "")), 
                                        type="password")
        st.session_state.gemini_key = gemini_key_input
        gemini_model_input = st.text_input("Model Name", 
                                          value=st.session_state.get("gemini_model", st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash")))
        st.session_state.gemini_model = gemini_model_input
        
        if st.button("🔌 Test Gemini"):
            success, msg = test_gemini_connection(st.session_state.gemini_key.strip(), st.session_state.gemini_model.strip())
            if success: st.sidebar.success(msg)
            else: st.sidebar.error(msg)
            
    else: # OpenRouter
        or_key_input = st.text_input("OpenRouter API Key", 
                                    value=st.session_state.get("or_key", st.secrets.get("OPENROUTER_API_KEY", "")), 
                                    type="password")
        st.session_state.or_key = or_key_input
        or_model_input = st.text_input("Model Name", 
                                      value=st.session_state.get("or_model", st.secrets.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")))
        st.session_state.or_model = or_model_input
        
        if st.button("🔌 Test OpenRouter"):
            success, msg = test_openrouter_connection(st.session_state.or_key.strip(), st.session_state.or_model.strip())
            if success: st.sidebar.success(msg)
            else: st.sidebar.error(msg)

    st.divider()
    st.session_state.nc_api_user = st.text_input("Namecheap ApiUser", type="password")
    st.session_state.nc_api_key = st.text_input("Namecheap ApiKey", type="password")
    st.session_state.nc_username = st.text_input("Namecheap Username", type="password")

niche = st.sidebar.selectbox("Niche", ["Tech & AI", "Finance & SaaS", "E-commerce", "Creative & Arts", "Health & Wellness", "Real Estate"])
keywords = st.sidebar.text_input("🎯 Keywords (comma separated)", placeholder="e.g. fast, smart, secure")
num_per_tier = st.sidebar.slider("Domains per Tier", 5, 50, 15)
extensions = st.sidebar.multiselect("الامتدادات", [".com", ".net", ".org", ".io", ".ai", ".co", ".app", ".dev"], default=[".com", ".ai"])

use_llm = st.sidebar.checkbox("LLM Creative Boost", value=True)
use_availability = st.sidebar.checkbox("Auto Availability + Buy", value=True)

# ==================== TABS (4 تبويبات) ====================
tab1, tab2, tab_fav, tab3, tab4, tab5 = st.tabs(["🚀 Generator", "📚 Word Banks", "⭐ Favorites", "📊 History", "📦 My Portfolio", "📈 Stats"])

with tab1:
    st.title("🔥 Generator V4 – Auto Buy جاهز")
    
    # Bulk actions moved to top
    bulk_placeholder = st.empty()
    
    if st.button("🚀 Generate Domains", type="primary"):
        st.session_state.generating = True
        st.session_state.last_results = [] # Clear previous
        st.session_state.show_results = False
        st.rerun()
    
    if st.session_state.get("generating", False):
        with st.spinner("جاري التوليد والتقييم..."):
            names = generate_domains(niche, use_llm, keywords, num_per_tier)
            
            categories = {"🔥 Premium": [], "⚖️ Mid": [], "🧪 Experimental": []}
            for name in names:
                appr = appraise_name(name)
                categories[appr["tier"]].append((name, appr))
            
            # Save results to session state
            st.session_state.last_categories = categories
            st.session_state.generating = False
            st.session_state.show_results = True
            
            # Save to history session state
            for tier, items in categories.items():
                for name, appraisal in items:
                    st.session_state.history.append({
                        "Name": name, "Tier": tier, "Value": appraisal["value"], "Niche": niche, "Date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
            st.rerun()

    if st.session_state.get("show_results", False):
        categories = st.session_state.get("last_categories", {})
        all_generated_full = []
        bulk_placeholder = st.empty()

        for tier, items in categories.items():
            if items:
                items = items[:num_per_tier]
                st.subheader(f"{tier} Domains")
                for name, appraisal in items:
                    for ext in extensions:
                        full = f"{name}{ext}"
                        all_generated_full.append(full)
                        status = check_availability(full) if use_availability else ""
                        
                        col1, col2, col3 = st.columns([3,2,2])
                        with col1:
                            color = "green" if "Available" in status else "red"
                            st.markdown(f"**:{color}[{full}]**" if status else f"**{full}**")
                        with col2:
                            st.caption(f"{appraisal['value']} | {status}")
                        with col3:
                            sub_col1, sub_col2 = st.columns(2)
                            if "Available" in status:
                                with sub_col1:
                                    if st.button("🛒 Buy", key=f"buy_{full}"):
                                        url = f"https://www.namecheap.com/domains/registration/results/?domain={quote(full)}"
                                        webbrowser.open(url)
                                with sub_col2:
                                    if st.button("➕ Portfolio", key=f"add_{full}"):
                                        add_to_portfolio(full, name, ext, niche, appraisal["tier"], appraisal["value"])
                        
                        # Favorites button
                        if st.button("❤️" if full not in [f['domain'] for f in st.session_state.favorites] else "💖", key=f"fav_{full}"):
                            if full not in [f['domain'] for f in st.session_state.favorites]:
                                st.session_state.favorites.append({"domain": full, "tier": appraisal["tier"], "value": appraisal["value"], "niche": niche})
                                st.toast(f"✅ تمت إضافة {full} للمفضلة")
                            else:
                                st.session_state.favorites = [f for f in st.session_state.favorites if f['domain'] != full]
                                st.toast(f"🗑️ تمت إزالة {full} من المفضلة")
                            st.rerun()

        if all_generated_full:
            st.session_state.last_results = all_generated_full
            with bulk_placeholder.container():
                st.success(f"🎉 تم إيجاد {len(all_generated_full)} دومين.")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.text_area("📋 Copy All", value="\n".join(all_generated_full), height=100)
                with col_b:
                    st.download_button("📥 Download", data="\n".join(all_generated_full), file_name="domains.txt")
                with col_c:
                    if st.button("🧹 Clear Results"):
                        st.session_state.show_results = False
                        st.session_state.last_results = []
                        st.rerun()

with tab2:
    st.title("📚 Word Banks")
    
    col_save1, col_save2 = st.columns([1, 4])
    with col_save1:
        if st.button("💾 حفظ الكل في ملفات TXT", type="primary"):
            save_word_banks(st.session_state.word_banks)
            st.success("✅ تم حفظ جميع الكلمات في مجلد word_banks/")
    
    st.divider()
    # File Uploader to Overwrite Word Banks
    uploaded_file = st.file_uploader("📥 استيراد بنك كلمات من ملف .txt (سيقوم باستبدال الكلمات الحالية)", type="txt")
    if uploaded_file:
        content = uploaded_file.read().decode("utf-8")
        # Expecting lines like: category: word1, word2, ...
        new_banks = {}
        for line in content.split("\n"):
            if ":" in line:
                cat, words = line.split(":", 1)
                new_banks[cat.strip()] = [w.strip().lower() for w in words.split(",") if w.strip()]
        if new_banks:
            st.session_state.word_banks = new_banks
            st.success("✅ تم استيراد بنك الكلمات بنجاح!")
            st.rerun()

    st.info("💡 نصيحة: استخدم زر ✨ AI Boost لإضافة كلمات إبداعية بناءً على الـ Niche المختار.")
    cols = st.columns(2)
    for i, (cat, words) in enumerate(st.session_state.word_banks.items()):
        with cols[i % 2]:
            st.divider()
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"📂 {cat}")
            with c2:
                if st.button(f"✨ AI Boost", key=f"ai_btn_{cat}"):
                    with st.spinner("جاري التفكير..."):
                        suggestions = ai_suggest_words(niche, cat, words)
                        if suggestions:
                            new_list = list(set(words + [s.lower() for s in suggestions]))
                            st.session_state.word_banks[cat] = new_list
                            # Also update the text area's state to prevent immediate overwrite
                            st.session_state[f"area_{cat}"] = ", ".join(new_list)
                            st.success(f"✅ تم إضافة {len(suggestions)} كلمة جديدة لقسم {cat}!")
                            st.rerun()
                        else:
                            st.error("❌ لم نتمكن من الحصول على مقترحات. تأكد من الـ API Key")
                            
            new_words = st.text_area(f"كلمات قسم {cat}", value=", ".join(words), height=150, key=f"area_{cat}")
            st.session_state.word_banks[cat] = [w.strip().lower() for w in new_words.split(",") if w.strip()]

with tab_fav:
    st.title("⭐ Favorites List")
    if st.session_state.favorites:
        fav_df = pd.DataFrame(st.session_state.favorites)
        st.dataframe(fav_df, width='stretch')
        if st.button("🗑️ Clear All Favorites"):
            st.session_state.favorites = []
            st.rerun()
    else:
        st.info("لم تقم بإضافة أي دومينات للمفضلة بعد.")

with tab3:
    st.title("📊 History (Current Session)")
    if st.session_state.history:
        df_hist = pd.DataFrame(st.session_state.history)
        st.dataframe(df_hist, width='stretch')
        
        # Export Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_hist.to_excel(writer, index=False, sheet_name='History')
        st.download_button("📥 Download History (Excel)", data=output.getvalue(), file_name="domain_history.xlsx")
    else:
        st.info("لا يوجد سجل لهذه الجلسة بعد.")

with tab4:
    st.title("📦 My Domains Portfolio")
    df = get_portfolio()
    if not df.empty:
        st.dataframe(df, width='stretch')
        
        col1, col2 = st.columns(2)
        with col1:
            domain_to_buy = st.selectbox("اختر دومين لشرائه", df['full_domain'])
            if st.button("🛒 Buy Now"):
                webbrowser.open(f"https://www.namecheap.com/domains/registration/results/?domain={quote(domain_to_buy)}")
    else:
        st.info("الـ Portfolio فاضي – ابدأ توليد وأضف دومينات!")

with tab5:
    st.title("📈 Portfolio Stats")
    df = get_portfolio()
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Domains", len(df))
        col2.metric("Premium", len(df[df['appraisal_tier'].str.contains("Premium")]))
        col3.metric("Mid Tier", len(df[df['appraisal_tier'].str.contains("Mid")]))
        
        st.divider()
        st.subheader("Niche Distribution")
        st.bar_chart(df['niche'].value_counts())
    else:
        st.info("لا توجد بيانات للإحصائيات حالياً.")

st.divider()
st.caption("DomainTrade Pro V4 Ultimate • Portfolio DB • Auto-Buy Namecheap • Streamlit Cloud Ready")