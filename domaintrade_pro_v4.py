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
import webbrowser
from urllib.parse import quote
import io

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
    xai_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
    xai_model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-4.20-0309-reasoning")).strip()
    if not xai_key:
        return []
    try:
        client = OpenAI(
            api_key=xai_key,
            base_url="https://api.x.ai/v1",
        )
        prompt = f"""Generate {count} unique, brandable, 1-word or 2-word domain names for the '{niche}' niche.
        Avoid these already generated names: {existing}.
        Focus on short, memorable, and pronounceable names.
        Return ONLY a JSON list of strings, for example: ["name1", "name2", ...]"""
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=xai_model,
            response_format={"type": "json_object"}
        )
        content = chat_completion.choices[0].message.content
        data = json.loads(content)
        return data.get("domains", data.get("names", list(data.values())[0]))
    except Exception as e:
        st.sidebar.error(f"xAI Error: {e}")
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

# ==================== SESSION STATE & SIDEBAR ====================
if "word_banks" not in st.session_state:
    st.session_state.word_banks = {
        "abstract": ["nexus", "quantum", "vertex", "prime", "zenith", "arc", "flux", "core", "omni", "nova"],
        "power": ["boost", "pro", "master", "elite", "ultra", "max", "hyper", "mega", "titan", "force"],
        "tech": ["logic", "code", "dev", "sys", "net", "cloud", "ai", "stack", "bit", "data"],
        "finance": ["pay", "coin", "fund", "equity", "trust", "cap", "wealth", "asset", "bank", "lend"],
        "creative": ["spark", "flow", "mind", "idea", "vision", "art", "pixel", "canvas", "design", "studio"],
        "short_prefixes": ["get", "my", "the", "re", "go", "on", "up", "in", "it", "be"]
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "favorites" not in st.session_state:
    st.session_state.favorites = []

def test_xai_connection(api_key, model):
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        client.chat.completions.create(
            messages=[{"role": "user", "content": "ping"}],
            model=model,
            max_tokens=5
        )
        return True, f"✅ تم الربط بـ {model} بنجاح!"
    except Exception as e:
        return False, f"❌ فشل الربط: {e}"

def ai_suggest_words(niche, category, current_words):
    xai_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
    xai_model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-4.20-0309-reasoning")).strip()
    if not xai_key:
        return []
    try:
        client = OpenAI(
            api_key=xai_key,
            base_url="https://api.x.ai/v1",
        )
        prompt = f"""As a domain branding expert, suggest 15 new, creative, and catchy words for the '{category}' category in the '{niche}' niche.
        Existing words: {current_words}.
        Return ONLY a JSON list of strings."""
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=xai_model,
            response_format={"type": "json_object"}
        )
        content = chat_completion.choices[0].message.content
        data = json.loads(content)
        return data.get("words", data.get("suggestions", list(data.values())[0]))
    except Exception as e:
        st.sidebar.error(f"xAI Error: {e}")
        return []

st.sidebar.title("🔧 DomainTrade Pro V4")
st.sidebar.caption("SaaS Ready – Portfolio + Auto Buy")

# API Keys (Streamlit Secrets في الـ Cloud)
with st.sidebar.expander("🔑 API Keys", expanded=True):
    # Check if keys are in st.secrets
    has_xai_secret = "XAI_API_KEY" in st.secrets
    
    xai_key_input = st.text_input("Grok (xAI) API Key", 
                                 value=st.session_state.get("xai_key", st.secrets.get("XAI_API_KEY", "grokApiKey-asa")), 
                                 type="password",
                                 help="سيتم استخدامه إذا لم يكن موجوداً في Secrets" if has_xai_secret else "")
    st.session_state.xai_key = xai_key_input
    
    # Model Selector
    xai_model_input = st.text_input("Model Name", 
                                    value=st.session_state.get("xai_model", st.secrets.get("XAI_MODEL", "grok-4.20-0309-reasoning")),
                                    placeholder="e.g. grok-2, grok-beta, etc.")
    st.session_state.xai_model = xai_model_input
    
    if has_xai_secret:
        st.sidebar.info("💡 تم الكشف عن مفتاح API في Secrets.")

    if st.button("🔌 Test Connection"):
        xai_key_clean = st.session_state.xai_key.strip()
        xai_model_clean = st.session_state.xai_model.strip()
        if xai_key_clean:
            with st.spinner("جاري التحقق من xAI..."):
                success, msg = test_xai_connection(xai_key_clean, xai_model_clean)
                if success: st.sidebar.success(msg)
                else: st.sidebar.error(msg)
        else:
            st.sidebar.warning("برجاء إدخال المفتاح أولاً")
            
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
        with st.spinner("جاري التوليد والتقييم..."):
            names = generate_domains(niche, use_llm, keywords, num_per_tier)
            
            categories = {"🔥 Premium": [], "⚖️ Mid": [], "🧪 Experimental": []}
            all_generated_full = []
            
            for name in names:
                appr = appraise_name(name)
                categories[appr["tier"]].append((name, appr))
            
            for tier, items in categories.items():
                if items:
                    # Limit each tier to user requested amount
                    items = items[:num_per_tier]
                    st.subheader(f"{tier} Domains")
                    for name, appraisal in items:
                        for ext in extensions:
                            full = f"{name}{ext}"
                            all_generated_full.append(full)
                            status = check_availability(full) if use_availability else ""
                            
                            # Real-time update of bulk copy (every 5 domains)
                            if len(all_generated_full) % 5 == 0:
                                with bulk_placeholder.container():
                                    st.caption(f"🔄 جاري التحديث... ({len(all_generated_full)} دومين)")
                                    st.text_area("Copy All Domains (Live Update)", value="\n".join(all_generated_full), height=150)
                            
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
                                    st.session_state.favorites.append({
                                        "domain": full, "tier": appraisal["tier"], "value": appraisal["value"], "niche": niche
                                    })
                                    st.toast(f"✅ تمت إضافة {full} للمفضلة")
                                    st.rerun()
                                else:
                                    st.session_state.favorites = [f for f in st.session_state.favorites if f['domain'] != full]
                                    st.toast(f"🗑️ تمت إزالة {full} من المفضلة")
                                    st.rerun()

            if all_generated_full:
                st.session_state.last_results = all_generated_full # Store for persistence if needed
                with bulk_placeholder.container():
                    st.success(f"🎉 اكتمل التوليد! تم إيجاد {len(all_generated_full)} دومين.")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.text_area("📋 Copy All Domains", value="\n".join(all_generated_full), height=150)
                    with col_b:
                        st.download_button("📥 Download List (.txt)", data="\n".join(all_generated_full), file_name="domains_list.txt")
                        if st.button("🧹 Clear Results"):
                            st.rerun() # This will refresh and clear the 'if button' block

            # Save to history session state
            for tier, items in categories.items():
                for name, appraisal in items:
                    st.session_state.history.append({
                        "Name": name,
                        "Tier": tier,
                        "Value": appraisal["value"],
                        "Niche": niche,
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })

with tab2:
    st.title("📚 Word Banks")
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
                            st.session_state.word_banks[cat] = list(set(words + [s.lower() for s in suggestions]))
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