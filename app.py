"""Streamlit entrypoint for the domain generation and analysis app."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from availability import (
    LIKELY_REGISTERED,
    check_availability_details,
)
from constants import (
    AI_PROVIDERS,
    APP_ICON,
    APP_LAYOUT,
    APP_TITLE,
    DEFAULT_AI_PROVIDER,
    DEFAULT_EXTENSIONS,
    DEFAULT_SCORING_PROFILE,
    EXTENSION_OPTIONS,
    NICHE_OPTIONS,
    SCORING_PROFILES,
)
from generator import generate_domains
from providers import ai_suggest_keywords_from_topic, ai_suggest_words, preflight_generation_model, test_connection
from scoring import evaluate_domain, get_profile
from storage import add_to_portfolio, get_portfolio, init_db
from utils.browser import open_namecheap_purchase
from utils.export import dataframe_to_excel_bytes
from utils.session import initialize_session_state, reset_all_app_data
from utils.word_banks import deduplicate_words, save_word_banks


GRADE_ORDER = ["A+", "A", "B", "C", "D", "Reject"]


def appraisal_to_dict(appraisal) -> dict:
    """Convert a structured appraisal dataclass into a session-friendly dict."""
    return {
        "domain": appraisal.domain,
        "name": appraisal.name,
        "tld": appraisal.tld,
        "profile": appraisal.profile,
        "niche": "",
        "final_score": appraisal.final_score,
        "grade": appraisal.grade,
        "tier": appraisal.tier,
        "value": appraisal.value,
        "subscores": dict(appraisal.subscores),
        "flags": list(appraisal.flags),
        "warnings": list(appraisal.warnings),
        "explanation": appraisal.explanation,
        "rejected": appraisal.rejected,
        "method": "unknown",
        "source_name": "",
        "is_transformed": False,
        "improvement_delta": 0,
        "source_domain": "",
    }


def build_results_table(appraisals: list[dict], status_map: dict[str, str]) -> pd.DataFrame:
    """Build a compact comparison table for generated domains."""
    rows = []
    for appraisal in appraisals:
        rows.append(
            {
                "Domain": appraisal["domain"],
                "Niche": appraisal.get("niche", ""),
                "Extension": appraisal["tld"],
                "Score": appraisal["final_score"],
                "Grade": appraisal["grade"],
                "Method": str(appraisal.get("method", "")).title(),
                "Delta": appraisal.get("improvement_delta", 0),
                "Profile": get_profile(appraisal["profile"]).label,
                "Availability": status_map.get(appraisal["domain"], ""),
                "Explanation": appraisal["explanation"],
            }
        )
    return pd.DataFrame(rows)


def build_transformation_table(appraisals: list[dict]) -> pd.DataFrame:
    """Build a before/after view for transformed candidates."""
    rows = []
    for appraisal in appraisals:
        if not appraisal.get("is_transformed"):
            continue
        rows.append(
            {
                "Improved Domain": appraisal["domain"],
                "Method": str(appraisal.get("method", "")).title(),
                "From": appraisal.get("source_domain", ""),
                "Delta": appraisal.get("improvement_delta", 0),
                "Score": appraisal["final_score"],
                "Grade": appraisal["grade"],
                "Profile": get_profile(appraisal["profile"]).label,
                "Niche": appraisal.get("niche", ""),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Delta", "Score"], ascending=[False, False])


def prepare_favorites_dataframe() -> pd.DataFrame:
    """Create a readable favorites table for investor comparison."""
    favorites_df = pd.DataFrame(st.session_state.favorites)
    if favorites_df.empty:
        return favorites_df
    preferred_columns = [
        "domain",
        "grade",
        "score",
        "profile",
        "value",
        "niche",
        "explanation",
    ]
    favorites_df = favorites_df[[column for column in preferred_columns if column in favorites_df.columns]]
    return favorites_df.rename(
        columns={
            "domain": "Domain",
            "grade": "Grade",
            "score": "Score",
            "profile": "Profile",
            "value": "Value",
            "niche": "Niche",
            "explanation": "Explanation",
        }
    )


def prepare_history_dataframe() -> pd.DataFrame:
    """Create a readable history table with score context."""
    history_df = pd.DataFrame(st.session_state.history)
    if history_df.empty:
        return history_df
    preferred_columns = [
        "Domain",
        "Extension",
        "Grade",
        "Score",
        "Method",
        "Profile",
        "Value",
        "Niche",
        "Explanation",
        "Date",
    ]
    available_columns = [column for column in preferred_columns if column in history_df.columns]
    history_df = history_df[available_columns]
    if "Score" in history_df.columns:
        history_df = history_df.sort_values(["Score", "Date"], ascending=[False, False])
    return history_df


def prepare_portfolio_dataframe(portfolio_df: pd.DataFrame) -> pd.DataFrame:
    """Create a readable portfolio table with score-facing fields first."""
    if portfolio_df.empty:
        return portfolio_df

    display_df = portfolio_df.copy()
    display_df["Grade"] = display_df["appraisal_tier"].fillna("").str.split(" · ").str[0]
    display_df["Tier Label"] = display_df["appraisal_tier"].fillna("").str.split(" · ").str[1]

    preferred_columns = [
        "full_domain",
        "Grade",
        "score",
        "scoring_profile",
        "appraisal_value",
        "niche",
        "explanation",
        "generated_date",
        "status",
    ]
    display_df = display_df[[column for column in preferred_columns if column in display_df.columns]]
    return display_df.rename(
        columns={
            "full_domain": "Domain",
            "score": "Score",
            "scoring_profile": "Profile",
            "appraisal_value": "Value",
            "niche": "Niche",
            "explanation": "Explanation",
            "generated_date": "Added",
            "status": "Availability",
        }
    )


def render_methodology_status(use_llm: bool, use_availability: bool) -> None:
    """Show an explicit status report for the current generation and filtering methodology."""
    llm_status = "Enabled" if use_llm else "Disabled"
    availability_status = "Enabled (display only, not in final score)" if use_availability else "Disabled"

    with st.expander("Methodology Status", expanded=False):
        st.markdown("### Transformations")
        st.markdown(
            "\n".join(
                [
                    "- `Combine`: implemented via word + word and keyword + word generation.",
                    "- `Twist`: implemented as a phonetic brand variation step on base candidates.",
                    "- `Cut`: implemented as a shortening step on base candidates.",
                    f"- `Invent`: implemented through an internal invented-name generator, with optional `LLM Creative Boost`. LLM status: {llm_status}.",
                ]
            )
        )
        st.caption("Current generator now mixes structured combining, deterministic transformations, and optional LLM ideation.")

        st.markdown("### Filters")
        st.markdown(
            "\n".join(
                [
                    "- `Pronunciation score`: implemented.",
                    "- `Brand score`: implemented.",
                    "- `Market fit`: implemented.",
                    f"- `Availability`: {availability_status}.",
                    "- `Buyer probability`: partially covered through `liquidity score`, not yet a separate explicit score.",
                ]
            )
        )
        st.caption("Hard filters already penalize length, ugly joins, repeated segments, spam patterns, weak endings, and profile/TLD mismatch.")

        st.markdown("### Gaps")
        st.markdown(
            "\n".join(
                [
                    "- No before/after comparison for original idea versus improved variant yet.",
                    "- No automatic improvement suggestions yet.",
                    "- Availability is shown in the UI, but it does not currently modify the final score.",
                    "- Improvement comparison is available, but it is still score-based rather than explanation-driven coaching.",
                ]
            )
        )


def render_sidebar() -> tuple[list[str], list[str], str, int, list[str], bool, bool]:
    """Render sidebar controls and return selected generator and scoring options."""
    if st.sidebar.button("🗑️ Reset All App Data", type="secondary"):
        reset_all_app_data()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.title("🔧 DomainTrade Pro V5")
    st.sidebar.caption("Smarter Scoring · Unified AI · Clean Code")

    with st.sidebar.expander("🔑 AI Settings & Keys", expanded=True):
        current_provider = st.session_state.get("ai_provider", DEFAULT_AI_PROVIDER)
        st.session_state.ai_provider = st.selectbox(
            "AI Provider",
            AI_PROVIDERS,
            index=AI_PROVIDERS.index(current_provider),
        )
        st.divider()

        if st.session_state.ai_provider == "xAI (Grok)":
            st.session_state.xai_key = st.text_input(
                "Grok (xAI) API Key",
                value=st.session_state.get("xai_key", st.secrets.get("XAI_API_KEY", "")),
                type="password",
            )
            st.session_state.xai_model = st.text_input(
                "Model Name",
                value=st.session_state.get("xai_model", st.secrets.get("XAI_MODEL", "grok-3-mini")),
            )
            if st.button("🔌 Test xAI"):
                ok, msg = test_connection("xAI (Grok)", st.session_state.xai_key, st.session_state.xai_model)
                (st.sidebar.success if ok else st.sidebar.error)(msg)

        elif st.session_state.ai_provider == "Google Gemini":
            st.session_state.gemini_key = st.text_input(
                "Gemini API Key",
                value=st.session_state.get("gemini_key", st.secrets.get("GEMINI_API_KEY", "")),
                type="password",
            )
            st.session_state.gemini_model = st.text_input(
                "Model Name",
                value=st.session_state.get("gemini_model", st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash")),
            )
            if st.button("🔌 Test Gemini"):
                ok, msg = test_connection("Google Gemini", st.session_state.gemini_key, st.session_state.gemini_model)
                (st.sidebar.success if ok else st.sidebar.error)(msg)

        else:
            st.session_state.or_key = st.text_input(
                "OpenRouter API Key",
                value=st.session_state.get("or_key", st.secrets.get("OPENROUTER_API_KEY", "")),
                type="password",
            )
            st.session_state.or_model = st.text_input(
                "Model Name",
                value=st.session_state.get(
                    "or_model",
                    st.secrets.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001"),
                ),
            )
            if st.button("🔌 Test OpenRouter"):
                ok, msg = test_connection("OpenRouter", st.session_state.or_key, st.session_state.or_model)
                (st.sidebar.success if ok else st.sidebar.error)(msg)

        st.divider()
        st.session_state.nc_api_user = st.text_input("Namecheap ApiUser", type="password")
        st.session_state.nc_api_key = st.text_input("Namecheap ApiKey", type="password")
        st.session_state.nc_username = st.text_input("Namecheap Username", type="password")

    selected_niches = st.sidebar.multiselect(
        "Niche",
        NICHE_OPTIONS,
        default=st.session_state.get("selected_niches", [NICHE_OPTIONS[0]]),
    )
    if not selected_niches:
        selected_niches = [NICHE_OPTIONS[0]]
    st.session_state.selected_niches = selected_niches

    selected_profiles = st.sidebar.multiselect(
        "Scoring Profile",
        SCORING_PROFILES,
        default=st.session_state.get("selected_profiles", [DEFAULT_SCORING_PROFILE]),
        format_func=lambda key: get_profile(key).label,
    )
    if not selected_profiles:
        selected_profiles = [DEFAULT_SCORING_PROFILE]
    st.session_state.selected_profiles = selected_profiles
    st.session_state.scoring_profile = selected_profiles[0]

    if len(selected_profiles) == 1:
        st.sidebar.caption(get_profile(selected_profiles[0]).description)
    else:
        st.sidebar.caption(f"{len(selected_profiles)} scoring profiles selected.")

    pending_keywords = st.session_state.pop("pending_keywords", None)
    if pending_keywords is not None:
        st.session_state["keywords"] = pending_keywords

    keywords = st.sidebar.text_input(
        "🎯 Keywords (comma separated)",
        placeholder="e.g. fast, smart, secure",
        key="keywords",
    )
    topic_prompt = st.sidebar.text_area(
        "🧠 Topic / Brief for AI Keyword Suggestions",
        placeholder="e.g. منصة AI تساعد المطاعم على الرد التلقائي والحجوزات",
        height=90,
        key="keyword_topic",
    )
    if st.sidebar.button("✨ Suggest Keywords with AI", help="Generate keyword seeds from your topic, niches, and selected profiles."):
        if not topic_prompt.strip():
            st.sidebar.warning("اكتب جملة أو موضوع أولًا.")
        else:
            with st.spinner("جاري اقتراح كلمات مناسبة..."):
                suggestions = ai_suggest_keywords_from_topic(
                    topic=topic_prompt,
                    niches=selected_niches,
                    profiles=selected_profiles,
                    existing_keywords=[keyword.strip() for keyword in keywords.split(",") if keyword.strip()],
                )
            if suggestions:
                merged_keywords = deduplicate_words(
                    [keyword.strip().lower() for keyword in keywords.split(",") if keyword.strip()] + suggestions
                )
                st.session_state["pending_keywords"] = ", ".join(merged_keywords)
                st.sidebar.success(f"✅ تم اقتراح {len(suggestions)} كلمات")
                st.rerun()
            else:
                st.sidebar.error("❌ لم أتمكن من استخراج كلمات مناسبة. تأكد من الـ API Key أو جرّب وصفًا أوضح.")
    num_per_tier = st.sidebar.slider("Max domains shown per grade", 5, 50, 15)
    st.sidebar.caption("العدد هنا هو حد أقصى لكل Grade بعد التقييم، وليس إجمالي النتائج قبل الفلترة.")
    extensions = st.sidebar.multiselect("الامتدادات", EXTENSION_OPTIONS, default=DEFAULT_EXTENSIONS)
    use_llm = st.sidebar.checkbox("LLM Creative Boost", value=True)
    use_availability = st.sidebar.checkbox("Heuristic Availability Check", value=True)
    if use_availability:
        st.sidebar.caption("Uses conservative WHOIS/DNS signals for the exact domain. Unknown is preferred over false availability claims.")
    return selected_niches, selected_profiles, keywords, num_per_tier, extensions, use_llm, use_availability


def render_generator_tab(
    niches: list[str],
    scoring_profiles: list[str],
    keywords: str,
    num_per_tier: int,
    extensions: list[str],
    use_llm: bool,
    use_availability: bool,
) -> None:
    """Render the main domain generation workflow."""
    st.title("🔥 DomainTrade Pro V5 — Professional Scoring")
    profile_labels = ", ".join(get_profile(profile).label for profile in scoring_profiles)
    niche_labels = ", ".join(niches)
    st.caption(f"Niches: {niche_labels} · Profiles: {profile_labels}")
    render_methodology_status(use_llm=use_llm, use_availability=use_availability)
    if st.session_state.get("generation_notice"):
        notice = st.session_state["generation_notice"]
        if st.session_state.get("generation_use_llm", False):
            st.info(notice)
        else:
            st.warning(notice)

    if st.button("🚀 Generate Domains", type="primary"):
        effective_use_llm = use_llm
        if use_llm:
            llm_ready, generation_notice = preflight_generation_model()
            effective_use_llm = llm_ready
            st.session_state.generation_notice = generation_notice
        else:
            st.session_state.generation_notice = "سيتم التوليد من خلال النظام الداخلي فقط لأن LLM Creative Boost غير مفعّل."
        st.session_state.generation_use_llm = effective_use_llm
        st.session_state.generating = True
        st.session_state.last_results = []
        st.session_state.show_results = False
        st.rerun()

    if st.session_state.get("generating", False):
        with st.spinner("جاري التوليد والتقييم الاحترافي..."):
            effective_use_llm = st.session_state.get("generation_use_llm", False)
            generated_candidates_map: dict[str, dict] = {}
            for niche in niches:
                for candidate in generate_domains(
                    niche=niche,
                    use_llm=effective_use_llm,
                    word_banks=st.session_state.word_banks,
                    keywords_str=keywords,
                    num_per_tier=num_per_tier,
                ):
                    candidate_name = candidate["name"]
                    if candidate_name not in generated_candidates_map:
                        generated_candidates_map[candidate_name] = candidate

            generated_candidates = list(generated_candidates_map.values())
            st.session_state.last_generation_candidate_count = len(generated_candidates)
            categories = {grade: [] for grade in GRADE_ORDER}
            history_rows = []
            appraisal_records: list[dict] = []
            appraisal_lookup: dict[tuple[str, str, str, str], dict] = {}

            for niche in niches:
                for candidate in generated_candidates:
                    name = candidate["name"]
                    for ext in extensions:
                        full_domain = f"{name}{ext}"
                        for scoring_profile in scoring_profiles:
                            profile_config = get_profile(scoring_profile)
                            appraisal = evaluate_domain(
                                full_domain,
                                profile=scoring_profile,
                                niche=niche,
                                word_banks=st.session_state.word_banks,
                            )
                            appraisal_dict = appraisal_to_dict(appraisal)
                            appraisal_dict["niche"] = niche
                            appraisal_dict["method"] = candidate.get("method", "combine")
                            appraisal_dict["source_name"] = candidate.get("source_name", "")
                            appraisal_dict["is_transformed"] = candidate.get("is_transformed", False)
                            appraisal_records.append(appraisal_dict)
                            appraisal_lookup[(niche, scoring_profile, ext, name)] = appraisal_dict
                            history_rows.append(
                                {
                                    "Domain": full_domain,
                                    "Name": name,
                                    "Extension": ext,
                                    "Grade": appraisal.grade,
                                    "Score": appraisal.final_score,
                                    "Method": str(candidate.get("method", "combine")).title(),
                                    "Profile": profile_config.label,
                                    "Value": appraisal.value,
                                    "Niche": niche,
                                    "Explanation": appraisal.explanation,
                                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                }
                            )

            for appraisal_dict in appraisal_records:
                if appraisal_dict["is_transformed"] and appraisal_dict["source_name"]:
                    source_key = (
                        appraisal_dict["niche"],
                        appraisal_dict["profile"],
                        appraisal_dict["tld"],
                        appraisal_dict["source_name"],
                    )
                    source_appraisal = appraisal_lookup.get(source_key)
                    if source_appraisal:
                        appraisal_dict["source_domain"] = source_appraisal["domain"]
                        appraisal_dict["improvement_delta"] = appraisal_dict["final_score"] - source_appraisal["final_score"]

                categories[appraisal_dict["grade"]].append(appraisal_dict)

            for grade in categories:
                categories[grade].sort(key=lambda item: item["final_score"], reverse=True)

            st.session_state.last_categories = categories
            st.session_state.history.extend(history_rows)
            st.session_state.generating = False
            st.session_state.show_results = True
        st.rerun()

    if st.session_state.get("show_results", False):
        categories = st.session_state.get("last_categories", {})
        all_generated_full: list[str] = []
        comparison_appraisals: list[dict] = []
        status_map: dict[str, str] = {}
        candidate_count = st.session_state.get("last_generation_candidate_count", 0)
        st.caption(f"Raw candidate pool before scoring: {candidate_count}")

        for grade in GRADE_ORDER:
            items = categories.get(grade, [])[:num_per_tier]
            if not items:
                continue

            st.subheader(f"{grade} Domains")
            for item_index, appraisal in enumerate(items):
                full_domain = appraisal["domain"]
                row_key = f"{grade}_{item_index}_{full_domain}"
                all_generated_full.append(full_domain)
                comparison_appraisals.append(appraisal)
                availability_result = check_availability_details(full_domain) if use_availability else None
                status = availability_result.label if availability_result else ""
                status_map[full_domain] = status
                col1, col2, col3, col4 = st.columns([3, 1.2, 2, 2])
                with col1:
                    color = "red" if availability_result and availability_result.status == LIKELY_REGISTERED else "gray"
                    st.markdown(f"**:{color}[{full_domain}]**" if status else f"**{full_domain}**")
                    st.caption(appraisal["explanation"])
                    st.caption(f"Niche: {appraisal.get('niche', '')} · Profile: {get_profile(appraisal['profile']).label}")
                    if appraisal.get("is_transformed"):
                        delta = appraisal.get("improvement_delta", 0)
                        delta_label = f"{delta:+d}" if isinstance(delta, int) else str(delta)
                        st.caption(
                            f"Method: {str(appraisal.get('method', '')).title()} · "
                            f"From: {appraisal.get('source_domain', appraisal.get('source_name', ''))} · "
                            f"Delta: {delta_label}"
                        )
                    else:
                        st.caption(f"Method: {str(appraisal.get('method', '')).title()}")
                    if availability_result:
                        st.caption(f"Availability: {availability_result.label} · {availability_result.detail}")
                    if appraisal["warnings"]:
                        st.caption("Warnings: " + " · ".join(appraisal["warnings"][:2]))
                with col2:
                    st.caption(f"Grade {appraisal['grade']}")
                    st.caption(f"⭐ {appraisal['final_score']}/100")
                with col3:
                    st.caption(appraisal["value"])
                    st.caption(status or appraisal["tier"])
                with col4:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("Quick Link", key=f"buy_{row_key}", help="Quick Buy Link: open a registrar search page for this exact domain"):
                            open_namecheap_purchase(full_domain)
                    with c2:
                        if st.button("➕", key=f"add_{row_key}", help="Add to Portfolio"):
                            inserted = add_to_portfolio(
                                full_domain,
                                appraisal["name"],
                                appraisal["tld"],
                                appraisal.get("niche", ""),
                                f"{appraisal['grade']} · {appraisal['tier']}",
                                appraisal["value"],
                                appraisal["final_score"],
                                scoring_profile=get_profile(appraisal["profile"]).label,
                                explanation=appraisal["explanation"],
                                status=status or "Not checked",
                            )
                            if inserted:
                                st.success(f"✅ {full_domain} تمت إضافته للـ Portfolio")
                            else:
                                st.info("الدومين موجود بالفعل")
                    with c3:
                        is_favorite = full_domain in [fav["domain"] for fav in st.session_state.favorites]
                        if st.button("💖" if is_favorite else "🤍", key=f"fav_{row_key}"):
                            if not is_favorite:
                                st.session_state.favorites.append(
                                    {
                                        "domain": full_domain,
                                        "grade": appraisal["grade"],
                                        "score": appraisal["final_score"],
                                        "value": appraisal["value"],
                                        "profile": get_profile(appraisal["profile"]).label,
                                        "niche": appraisal.get("niche", ""),
                                        "explanation": appraisal["explanation"],
                                    }
                                )
                                st.toast(f"✅ تمت إضافة {full_domain} للمفضلة")
                            else:
                                st.session_state.favorites = [
                                    favorite for favorite in st.session_state.favorites if favorite["domain"] != full_domain
                                ]
                                st.toast(f"🗑️ تمت إزالة {full_domain} من المفضلة")
                            st.rerun()

                with st.expander(f"Why {full_domain}?", expanded=False):
                    st.write(f"Niche: {appraisal.get('niche', '')}")
                    st.write(f"Profile: {get_profile(appraisal['profile']).label}")
                    st.write(f"Method: {str(appraisal.get('method', '')).title()}")
                    if appraisal.get("is_transformed"):
                        st.write(f"Source: {appraisal.get('source_domain', appraisal.get('source_name', ''))}")
                        st.write(f"Improvement Delta: {appraisal.get('improvement_delta', 0):+d}")
                    st.write(f"Flags: {', '.join(appraisal['flags']) if appraisal['flags'] else 'None'}")
                    st.write(f"Warnings: {', '.join(appraisal['warnings']) if appraisal['warnings'] else 'None'}")
                    st.json(appraisal["subscores"])

        if all_generated_full:
            st.session_state.last_results = all_generated_full
            comparison_df = build_results_table(comparison_appraisals, status_map)
            transformation_df = build_transformation_table(comparison_appraisals)
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            summary_col1.metric("Compared Domains", len(comparison_df))
            summary_col2.metric(
                "Average Score",
                f"{comparison_df['Score'].mean():.0f}/100" if not comparison_df.empty else "N/A",
            )
            summary_col3.metric(
                "A Range",
                int(comparison_df["Grade"].isin(["A+", "A"]).sum()) if not comparison_df.empty else 0,
            )
            summary_col4.metric(
                "Warnings",
                int(sum(1 for appraisal in comparison_appraisals if appraisal["warnings"])),
            )
            st.caption("Comparison view keeps score, grade, profile, and explanation aligned for faster investor review.")
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)
            if not transformation_df.empty:
                st.caption("Before/after view highlights transformed candidates against their source names.")
                st.dataframe(transformation_df, use_container_width=True, hide_index=True)
            st.divider()
            st.success(f"🎉 تم تقييم {len(all_generated_full)} دومين.")
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


def render_word_banks_tab(niches: list[str]) -> None:
    """Render word-bank editing and import workflows."""
    st.title("📚 Word Banks")
    niche_context = ", ".join(niches)

    col_save, _ = st.columns([1, 4])
    with col_save:
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
                category, words = line.split(":", 1)
                new_banks[category.strip()] = [word.strip().lower() for word in words.split(",") if word.strip()]
        if new_banks:
            st.session_state.word_banks = new_banks
            st.success("✅ تم استيراد بنك الكلمات بنجاح!")
            st.rerun()

    st.info("💡 نصيحة: استخدم ✨ AI Boost لإضافة كلمات إبداعية بناءً على الـ Niche المختار.")
    columns = st.columns(2)
    for index, (category, words) in enumerate(st.session_state.word_banks.items()):
        with columns[index % 2]:
            st.divider()
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.subheader(f"📂 {category}  ({len(words)} كلمة)")
            with c2:
                if st.button("✨ AI Boost", key=f"ai_btn_{category}"):
                    with st.spinner("جاري التفكير..."):
                        suggestions = ai_suggest_words(niche_context, category, words)
                        if suggestions:
                            new_list = deduplicate_words(words + [item.lower() for item in suggestions])
                            st.session_state.word_banks[category] = new_list
                            st.session_state[f"area_{category}"] = ", ".join(new_list)
                            st.success(f"✅ {len(suggestions)} كلمة جديدة!")
                            st.rerun()
                        else:
                            st.error("❌ تأكد من الـ API Key")
            with c3:
                if st.button("🗑️ مسح مكرر", key=f"dedup_{category}"):
                    st.session_state.word_banks[category] = deduplicate_words(words)
                    st.rerun()

            new_words = st.text_area(
                f"كلمات قسم {category}",
                value=", ".join(words),
                height=150,
                key=f"area_{category}",
            )
            updated = [word.strip().lower() for word in new_words.split(",") if word.strip()]
            st.session_state.word_banks[category] = deduplicate_words(updated)


def render_favorites_tab() -> None:
    """Render session favorites management."""
    st.title("⭐ Favorites List")
    if st.session_state.favorites:
        favorites_df = prepare_favorites_dataframe()
        st.dataframe(favorites_df, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear All Favorites"):
                st.session_state.favorites = []
                st.rerun()
        with col2:
            st.download_button(
                "📥 Download Favorites (Excel)",
                data=dataframe_to_excel_bytes(favorites_df, sheet_name="Favorites"),
                file_name="favorites.xlsx",
            )
    else:
        st.info("لم تقم بإضافة أي دومينات للمفضلة بعد.")


def render_history_tab() -> None:
    """Render current-session generation history."""
    st.title("📊 History (Current Session)")
    if st.session_state.history:
        history_df = prepare_history_dataframe()
        st.dataframe(history_df, use_container_width=True)
        st.download_button(
            "📥 Download History (Excel)",
            data=dataframe_to_excel_bytes(history_df, sheet_name="History"),
            file_name="domain_history.xlsx",
        )
    else:
        st.info("لا يوجد سجل لهذه الجلسة بعد.")



def render_portfolio_tab() -> None:
    """Render SQLite-backed portfolio management."""
    st.title("📦 My Domains Portfolio")
    portfolio_df = get_portfolio()
    if not portfolio_df.empty:
        display_df = prepare_portfolio_dataframe(portfolio_df)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        col1, col2 = st.columns(2)
        with col1:
            domain_to_buy = st.selectbox("اختر دومين لفتح رابط الشراء له", portfolio_df["full_domain"])
            if st.button("🔗 Quick Buy Link"):
                open_namecheap_purchase(domain_to_buy)
            st.caption("Opens a registrar search page only. It does not perform checkout automatically.")
        with col2:
            st.download_button(
                "📥 Export Portfolio (Excel)",
                data=dataframe_to_excel_bytes(portfolio_df, sheet_name="Portfolio"),
                file_name="portfolio.xlsx",
            )
    else:
        st.info("الـ Portfolio فاضي – ابدأ توليد وأضف دومينات!")



def render_stats_tab() -> None:
    """Render portfolio summary metrics and charts."""
    st.title("📈 Portfolio Stats")
    portfolio_df = get_portfolio()
    if not portfolio_df.empty:
        grade_series = portfolio_df["appraisal_tier"].fillna("").str.split(" · ").str[0]
        profile_series = portfolio_df["scoring_profile"].replace("", "Unknown") if "scoring_profile" in portfolio_df.columns else None
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Domains", len(portfolio_df))
        col2.metric("A Grades", int(grade_series.isin(["A+", "A"]).sum()))
        col3.metric("B Grades", int((grade_series == "B").sum()))
        col4.metric("Avg Score", f"{portfolio_df['score'].mean():.0f}/100" if "score" in portfolio_df.columns else "N/A")
        st.divider()
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.subheader("Niche Distribution")
            st.bar_chart(portfolio_df["niche"].value_counts())
        with col_b:
            st.subheader("Grade Distribution")
            st.bar_chart(grade_series.value_counts())
        with col_c:
            st.subheader("Profile Distribution")
            if profile_series is not None:
                st.bar_chart(profile_series.value_counts())
    else:
        st.info("لا توجد بيانات للإحصائيات حالياً.")



def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
    init_db()
    initialize_session_state()

    niches, scoring_profiles, keywords, num_per_tier, extensions, use_llm, use_availability = render_sidebar()
    tab1, tab2, tab_fav, tab3, tab4, tab5 = st.tabs([
        "🚀 Generator",
        "📚 Word Banks",
        "⭐ Favorites",
        "📊 History",
        "📦 My Portfolio",
        "📈 Stats",
    ])

    with tab1:
        render_generator_tab(niches, scoring_profiles, keywords, num_per_tier, extensions, use_llm, use_availability)
    with tab2:
        render_word_banks_tab(niches)
    with tab_fav:
        render_favorites_tab()
    with tab3:
        render_history_tab()
    with tab4:
        render_portfolio_tab()
    with tab5:
        render_stats_tab()

    st.divider()
    st.caption("DomainTrade Pro V5 · Professional Scoring Engine · Unified AI Engine · Portfolio DB")


if __name__ == "__main__":
    main()
