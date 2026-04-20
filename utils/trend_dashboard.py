"""Shared Trend Dashboard helpers for tabs and standalone Streamlit pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from jobs import run_domain_idea_job, run_ingest_job, run_processing_job
from providers import ai_refine_keywords, ai_refine_shortlist_domains, ai_refine_themes
from repositories.signals import get_signal_repository
from scoring import get_profile
from storage import add_to_portfolio
from utils.export import dataframe_to_excel_bytes


def prepare_themes_dataframe(themes: list[object]) -> pd.DataFrame:
    """Create a readable dataframe for extracted trend themes."""
    rows = []
    for theme in themes:
        rows.append(
            {
                "Theme": theme.canonical_name,
                "Classification": theme.classification.value.replace("_", " ").title(),
                "Momentum": round(float(theme.momentum_score), 2),
                "Signals": int(theme.source_count),
                "First Seen": theme.first_seen_at.date().isoformat(),
                "Last Seen": theme.last_seen_at.date().isoformat(),
                "Source Types": ", ".join(theme.source_types[:3]),
                "Sources": ", ".join(theme.source_names[:3]),
                "Source Breakdown": ", ".join(theme.source_breakdown[:4]),
                "Source Tags": ", ".join(theme.source_tags[:4]),
                "Source Entities": ", ".join(theme.source_entities[:4]),
                "Cluster Keys": ", ".join(theme.cluster_keys[:4]),
                "Evidence Titles": " | ".join(theme.evidence_titles[:3]),
                "Reason Highlights": " | ".join(theme.reason_highlights[:3]),
                "Related Terms": ", ".join(theme.related_terms[:5]),
                "Description": theme.description,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Momentum", "Signals"], ascending=[False, False])


def prepare_keyword_insights_dataframe(keywords: list[object]) -> pd.DataFrame:
    """Create a readable dataframe for keyword intelligence rows."""
    rows = []
    for keyword in keywords:
        rows.append(
            {
                "Keyword": keyword.keyword,
                "Type": keyword.keyword_type.replace("_", " ").title(),
                "Theme": keyword.theme_name,
                "Niche": keyword.niche,
                "Buyer Type": keyword.buyer_type,
                "Commercial": round(float(keyword.commercial_score), 2),
                "Novelty": round(float(keyword.novelty_score), 2),
                "Brandability": round(float(keyword.brandability_score), 2),
                "Notes": keyword.notes,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Commercial", "Brandability", "Novelty"], ascending=[False, False, False])


def prepare_domain_ideas_dataframe(domain_ideas: list[object]) -> pd.DataFrame:
    """Create a readable dataframe for generated domain opportunities."""
    recommendation_rank = {"buy": 2, "watch": 1, "skip": 0}
    review_bucket_rank = {"shortlist": 2, "watchlist": 1, "rejected": 0}
    rows = []
    for idea in domain_ideas:
        rows.append(
            {
                "Domain": f"{idea.domain_name}{idea.extension}",
                "Bucket": (idea.review_bucket or "watchlist").replace("_", " ").title(),
                "Recommendation": idea.recommendation.value.upper(),
                "Score": round(float(idea.score), 1),
                "Grade": idea.grade,
                "Theme": idea.source_theme,
                "Keyword": idea.keyword,
                "Niche": idea.niche,
                "Buyer Type": idea.buyer_type,
                "Profile": get_profile(idea.scoring_profile).label if idea.scoring_profile else "",
                "Value": idea.value_estimate,
                "Style": idea.style.replace("_", " ").title(),
                "Rationale": idea.rationale,
                "Risk Notes": " | ".join(idea.risk_notes[:2]),
                "Rejected Reason": idea.rejected_reason,
                "_bucket_rank": review_bucket_rank.get(idea.review_bucket or "", -1),
                "_rank": recommendation_rank.get(idea.recommendation.value, -1),
            }
        )
    if not rows:
        return pd.DataFrame()
    domain_ideas_df = pd.DataFrame(rows).sort_values(
        ["_bucket_rank", "_rank", "Score"],
        ascending=[False, False, False],
    )
    return domain_ideas_df.drop(columns=["_bucket_rank", "_rank"])


def prepare_refined_shortlist_dataframe(refined_items: list[dict[str, object]]) -> pd.DataFrame:
    """Create a readable dataframe for optional AI shortlist refinement output."""
    if not refined_items:
        return pd.DataFrame()

    verdict_rank = {"buy_now": 2, "hold_watch": 1, "reject": 0}
    priority_rank = {"high": 2, "medium": 1, "low": 0}
    rows = []
    for item in refined_items:
        rows.append(
            {
                "Domain": str(item.get("domain") or ""),
                "Investor Score": float(item.get("investor_score") or 0),
                "Verdict": str(item.get("verdict") or "").replace("_", " ").title(),
                "Priority": str(item.get("priority") or "").title(),
                "Buyer Angle": str(item.get("buyer_angle") or ""),
                "Why Good": str(item.get("why_good") or ""),
                "Risk Summary": str(item.get("risk_summary") or ""),
                "_verdict_rank": verdict_rank.get(str(item.get("verdict") or ""), -1),
                "_priority_rank": priority_rank.get(str(item.get("priority") or ""), -1),
            }
        )
    refined_df = pd.DataFrame(rows).sort_values(
        ["_verdict_rank", "_priority_rank", "Investor Score"],
        ascending=[False, False, False],
    )
    return refined_df.drop(columns=["_verdict_rank", "_priority_rank"])


def prepare_refined_themes_dataframe(refined_items: list[dict[str, object]]) -> pd.DataFrame:
    """Create a readable dataframe for optional AI theme refinement output."""
    if not refined_items:
        return pd.DataFrame()

    action_rank = {"promote": 2, "watch": 1, "drop": 0}
    rows = []
    for item in refined_items:
        rows.append(
            {
                "Theme": str(item.get("theme") or ""),
                "Confidence": float(item.get("confidence") or 0),
                "Action": str(item.get("action") or "").title(),
                "Suggested Niche": str(item.get("suggested_niche") or ""),
                "Buyer Angle": str(item.get("buyer_angle") or ""),
                "Domain Direction": str(item.get("domain_direction") or ""),
                "Why Now": str(item.get("why_now") or ""),
                "Risk Summary": str(item.get("risk_summary") or ""),
                "_action_rank": action_rank.get(str(item.get("action") or ""), -1),
            }
        )
    refined_df = pd.DataFrame(rows).sort_values(["_action_rank", "Confidence"], ascending=[False, False])
    return refined_df.drop(columns=["_action_rank"])


def prepare_refined_keywords_dataframe(refined_items: list[dict[str, object]]) -> pd.DataFrame:
    """Create a readable dataframe for optional AI keyword refinement output."""
    if not refined_items:
        return pd.DataFrame()

    action_rank = {"promote": 2, "keep": 1, "drop": 0}
    rows = []
    for item in refined_items:
        rows.append(
            {
                "Keyword": str(item.get("keyword") or ""),
                "Theme": str(item.get("theme") or ""),
                "Confidence": float(item.get("confidence") or 0),
                "Commercial Fit": float(item.get("commercial_fit") or 0),
                "Naming Fit": float(item.get("naming_fit") or 0),
                "Action": str(item.get("action") or "").title(),
                "Suggested Type": str(item.get("suggested_keyword_type") or ""),
                "Suggested Niche": str(item.get("suggested_niche") or ""),
                "Buyer Angle": str(item.get("buyer_angle") or ""),
                "Why Good": str(item.get("why_good") or ""),
                "Risk Summary": str(item.get("risk_summary") or ""),
                "_action_rank": action_rank.get(str(item.get("action") or ""), -1),
            }
        )
    refined_df = pd.DataFrame(rows).sort_values(
        ["_action_rank", "Commercial Fit", "Naming Fit", "Confidence"],
        ascending=[False, False, False, False],
    )
    return refined_df.drop(columns=["_action_rank"])


def _filter_domain_ideas_dataframe(domain_ideas_df: pd.DataFrame, bucket: str) -> pd.DataFrame:
    """Apply bucket, recommendation, theme, and niche filters for review workflows."""
    if domain_ideas_df.empty or "Bucket" not in domain_ideas_df.columns:
        return domain_ideas_df.copy()

    filtered_df = domain_ideas_df.copy()
    if bucket != "All":
        filtered_df = filtered_df[filtered_df["Bucket"] == bucket]
    if filtered_df.empty:
        return filtered_df

    key_prefix = bucket.lower().replace(" ", "_")
    recommendation_filter = st.selectbox(
        "Recommendation Filter",
        ["All", "BUY", "WATCH", "SKIP"],
        index=0,
        key=f"{key_prefix}_recommendation_filter",
    )
    theme_options = ["All"] + sorted(filtered_df["Theme"].dropna().astype(str).unique().tolist())
    theme_filter = st.selectbox(
        "Theme Filter",
        theme_options,
        index=0,
        key=f"{key_prefix}_theme_filter",
    )
    niche_options = ["All"] + sorted(filtered_df["Niche"].dropna().astype(str).unique().tolist())
    niche_filter = st.selectbox(
        "Niche Filter",
        niche_options,
        index=0,
        key=f"{key_prefix}_niche_filter",
    )

    if recommendation_filter != "All":
        filtered_df = filtered_df[filtered_df["Recommendation"] == recommendation_filter]
    if theme_filter != "All":
        filtered_df = filtered_df[filtered_df["Theme"] == theme_filter]
    if niche_filter != "All":
        filtered_df = filtered_df[filtered_df["Niche"] == niche_filter]
    return filtered_df


def _add_domain_idea_row_to_portfolio(selected_row: pd.Series) -> bool:
    """Persist one reviewed domain idea into the portfolio store."""
    full_domain = str(selected_row["Domain"])
    name, extension = full_domain.rsplit(".", 1)
    return add_to_portfolio(
        full_domain=full_domain,
        name=name,
        ext=f".{extension}",
        niche=str(selected_row["Niche"]),
        appraisal_tier=f"{selected_row['Grade']} · {selected_row['Recommendation'].title()}",
        appraisal_value=str(selected_row["Value"]),
        score=int(float(selected_row["Score"])),
        scoring_profile=str(selected_row["Profile"]),
        explanation=str(selected_row["Rationale"]),
        status="Not checked",
    )


def _render_shortlist_refinement(filtered_df: pd.DataFrame) -> None:
    """Run optional AI refinement only on the current shortlist slice."""
    st.divider()
    st.caption("Selective AI refinement runs only on the current shortlist slice, not on the full pipeline.")

    refinement_sample_df = filtered_df.head(8).copy()
    if refinement_sample_df.empty:
        st.info("لا توجد shortlist ideas متاحة حاليًا للـ AI refinement.")
        return

    if st.button("✨ Refine Current Shortlist With AI", key="shortlist_ai_refine"):
        with st.spinner("Running selective shortlist refinement..."):
            refined_items = ai_refine_shortlist_domains(refinement_sample_df.to_dict("records"))
        st.session_state.trend_shortlist_refinement = refined_items
        if refined_items:
            st.success("تم إنهاء AI refinement على shortlist الحالية.")
        else:
            st.info(st.session_state.get("last_llm_message", "تعذر الحصول على refinement من مزود الذكاء الاصطناعي."))

    refined_items = st.session_state.get("trend_shortlist_refinement", [])
    if not refined_items:
        return

    current_domains = set(filtered_df["Domain"].tolist())
    visible_items = [item for item in refined_items if str(item.get("domain") or "") in current_domains]
    refined_df = prepare_refined_shortlist_dataframe(visible_items)
    if refined_df.empty:
        st.info("آخر AI refinement لا يطابق shortlist الحالية بعد الفلاتر.")
        return

    st.caption("AI Shortlist Review")
    st.dataframe(refined_df, use_container_width=True, hide_index=True)
    st.download_button(
        "📥 Export AI Review (Excel)",
        data=dataframe_to_excel_bytes(refined_df, sheet_name="AIShortlist"),
        file_name="ai_shortlist_review.xlsx",
    )


def render_theme_refinement_panel(filtered_df: pd.DataFrame, *, key_prefix: str = "theme_refinement") -> None:
    """Run optional AI refinement only on the current visible theme slice."""
    st.divider()
    st.caption("Selective AI theme refinement runs only on the current visible theme slice.")

    refinement_sample_df = filtered_df.head(8).copy()
    if refinement_sample_df.empty:
        st.info("لا توجد themes متاحة حاليًا للـ AI refinement.")
        return

    if st.button("✨ Refine Current Themes With AI", key=f"{key_prefix}_ai_refine"):
        with st.spinner("Running selective theme refinement..."):
            refined_items = ai_refine_themes(refinement_sample_df.to_dict("records"))
        st.session_state.trend_theme_refinement = refined_items
        if refined_items:
            st.success("تم إنهاء AI refinement على theme slice الحالية.")
        else:
            st.info(st.session_state.get("last_llm_message", "تعذر الحصول على refinement من مزود الذكاء الاصطناعي."))

    refined_items = st.session_state.get("trend_theme_refinement", [])
    if not refined_items:
        return

    current_themes = set(filtered_df["Theme"].tolist())
    visible_items = [item for item in refined_items if str(item.get("theme") or "") in current_themes]
    refined_df = prepare_refined_themes_dataframe(visible_items)
    if refined_df.empty:
        st.info("آخر AI refinement لا يطابق theme slice الحالية بعد الفلاتر.")
        return

    st.caption("AI Theme Review")
    st.dataframe(refined_df, use_container_width=True, hide_index=True)
    st.download_button(
        "📥 Export AI Theme Review (Excel)",
        data=dataframe_to_excel_bytes(refined_df, sheet_name="AIThemes"),
        file_name="ai_theme_review.xlsx",
        key=f"{key_prefix}_export",
    )


def render_keyword_refinement_panel(filtered_df: pd.DataFrame, *, key_prefix: str = "keyword_refinement") -> None:
    """Run optional AI refinement only on the current visible keyword slice."""
    st.divider()
    st.caption("Selective AI keyword refinement runs only on the current visible keyword slice.")

    refinement_sample_df = filtered_df.head(10).copy()
    if refinement_sample_df.empty:
        st.info("لا توجد keywords متاحة حاليًا للـ AI refinement.")
        return

    if st.button("✨ Refine Current Keywords With AI", key=f"{key_prefix}_ai_refine"):
        with st.spinner("Running selective keyword refinement..."):
            refined_items = ai_refine_keywords(refinement_sample_df.to_dict("records"))
        st.session_state.trend_keyword_refinement = refined_items
        if refined_items:
            st.success("تم إنهاء AI refinement على keyword slice الحالية.")
        else:
            st.info(st.session_state.get("last_llm_message", "تعذر الحصول على refinement من مزود الذكاء الاصطناعي."))

    refined_items = st.session_state.get("trend_keyword_refinement", [])
    if not refined_items:
        return

    current_pairs = {
        (str(row["Keyword"]), str(row["Theme"]))
        for _, row in filtered_df[["Keyword", "Theme"]].iterrows()
    }
    visible_items = [
        item
        for item in refined_items
        if (str(item.get("keyword") or ""), str(item.get("theme") or "")) in current_pairs
    ]
    refined_df = prepare_refined_keywords_dataframe(visible_items)
    if refined_df.empty:
        st.info("آخر AI refinement لا يطابق keyword slice الحالية بعد الفلاتر.")
        return

    st.caption("AI Keyword Review")
    st.dataframe(refined_df, use_container_width=True, hide_index=True)
    st.download_button(
        "📥 Export AI Keyword Review (Excel)",
        data=dataframe_to_excel_bytes(refined_df, sheet_name="AIKeywords"),
        file_name="ai_keyword_review.xlsx",
        key=f"{key_prefix}_export",
    )


def render_domain_idea_review_table(
    domain_ideas_df: pd.DataFrame,
    *,
    bucket: str,
    empty_message: str,
    export_file_name: str,
    allow_portfolio_add: bool = False,
    allow_ai_refinement: bool = False,
) -> None:
    """Render one review lane for shortlist, watchlist, rejected, or all ideas."""
    filtered_df = _filter_domain_ideas_dataframe(domain_ideas_df, bucket)
    if filtered_df.empty:
        st.info(empty_message)
        return

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    st.download_button(
        "📥 Export (Excel)",
        data=dataframe_to_excel_bytes(filtered_df, sheet_name=bucket.replace(" ", "")[:31] or "DomainIdeas"),
        file_name=export_file_name,
    )

    if allow_portfolio_add:
        available_domains = filtered_df["Domain"].tolist()
        selected_domain = st.selectbox(
            "اختر domain idea لإضافتها للـ Portfolio",
            available_domains,
            key=f"{bucket.lower().replace(' ', '_')}_portfolio_domain",
        )
        if st.button("➕ Add Selected Idea To Portfolio", key=f"{bucket.lower().replace(' ', '_')}_portfolio_add"):
            selected_row = filtered_df[filtered_df["Domain"] == selected_domain].iloc[0]
            inserted = _add_domain_idea_row_to_portfolio(selected_row)
            if inserted:
                st.success(f"✅ {selected_domain} تمت إضافته للـ Portfolio")
            else:
                st.info("الدومين موجود بالفعل في الـ Portfolio")

    if allow_ai_refinement:
        _render_shortlist_refinement(filtered_df)


def render_trend_intelligence_tab() -> None:
    """Render the shared trend-intelligence dashboard tab."""
    st.title("🧭 Trend Intelligence")
    repository = get_signal_repository()

    st.caption("عرض سريع لنتائج الـ signal pipeline: themes, keywords, وdomain ideas.")
    st.caption("يمكنك أيضًا استخدام صفحات Streamlit الجديدة من الشريط الجانبي للوصول إلى overview/themes/shortlist/rejected بشكل مباشر.")
    action_col1, action_col2, action_col3, action_col4 = st.columns(4)

    if action_col1.button("⬇️ Run Ingest", help="Collect fresh raw signals from configured sources."):
        with st.spinner("Running ingest_signals..."):
            summary = run_ingest_job()
        st.success("تم تشغيل ingest_signals بنجاح.")
        st.json(summary)

    if action_col2.button("⚙️ Run Process", help="Clean, classify, and extract themes/keywords."):
        with st.spinner("Running process_signals..."):
            summary = run_processing_job()
        st.success("تم تشغيل process_signals بنجاح.")
        st.json(summary)

    if action_col3.button("💡 Generate Ideas", help="Generate scored domain ideas from stored themes and keywords."):
        with st.spinner("Running generate_domain_ideas..."):
            summary = run_domain_idea_job()
        st.success("تم تشغيل generate_domain_ideas بنجاح.")
        st.json(summary)

    if action_col4.button("🔄 Run Full Pipeline", help="Run ingest, process, then domain idea generation."):
        with st.spinner("Running full trend pipeline..."):
            ingest_summary = run_ingest_job()
            process_summary = run_processing_job()
            ideas_summary = run_domain_idea_job()
        st.success("تم تشغيل المسار الكامل بنجاح.")
        st.json({"ingest": ingest_summary, "process": process_summary, "domain_ideas": ideas_summary})

    themes = repository.list_themes()
    keywords = repository.list_keywords()
    domain_ideas = repository.list_domain_ideas()

    domain_ideas_df = prepare_domain_ideas_dataframe(domain_ideas)
    shortlist_count = int((domain_ideas_df["Bucket"] == "Shortlist").sum()) if not domain_ideas_df.empty else 0
    watchlist_count = int((domain_ideas_df["Bucket"] == "Watchlist").sum()) if not domain_ideas_df.empty else 0
    rejected_count = int((domain_ideas_df["Bucket"] == "Rejected").sum()) if not domain_ideas_df.empty else 0

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    metric_col1.metric("Themes", len(themes))
    metric_col2.metric("Keyword Insights", len(keywords))
    metric_col3.metric("Shortlist", shortlist_count)
    metric_col4.metric("Watchlist", watchlist_count)
    metric_col5.metric("Rejected", rejected_count)

    themes_df = prepare_themes_dataframe(themes)
    keywords_df = prepare_keyword_insights_dataframe(keywords)

    if not domain_ideas_df.empty:
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("Review Bucket Distribution")
            st.bar_chart(domain_ideas_df["Bucket"].value_counts())
        with chart_col2:
            st.caption("Top Themes In Review Queue")
            st.bar_chart(domain_ideas_df["Theme"].value_counts().head(10))

    theme_tab, keyword_tab, shortlist_tab, watchlist_tab, rejected_tab, all_ideas_tab = st.tabs(
        ["Themes", "Keywords", "Shortlist", "Watchlist", "Rejected", "All Ideas"]
    )

    with theme_tab:
        if themes_df.empty:
            st.info("لا توجد themes محفوظة بعد. شغّل `process_signals` أولًا.")
        else:
            st.dataframe(themes_df, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Export Themes (Excel)",
                data=dataframe_to_excel_bytes(themes_df, sheet_name="Themes"),
                file_name="trend_themes.xlsx",
            )
            render_theme_refinement_panel(themes_df, key_prefix="trend_tab_themes")

    with keyword_tab:
        if keywords_df.empty:
            st.info("لا توجد keyword insights محفوظة بعد. شغّل `process_signals` أولًا.")
        else:
            st.dataframe(keywords_df, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Export Keywords (Excel)",
                data=dataframe_to_excel_bytes(keywords_df, sheet_name="Keywords"),
                file_name="trend_keywords.xlsx",
            )
            render_keyword_refinement_panel(keywords_df, key_prefix="trend_tab_keywords")

    with shortlist_tab:
        render_domain_idea_review_table(
            domain_ideas_df,
            bucket="Shortlist",
            empty_message="لا توجد shortlist ideas بعد. شغّل `generate_domain_ideas` أو انتظر themes أقوى.",
            export_file_name="domain_shortlist.xlsx",
            allow_portfolio_add=True,
            allow_ai_refinement=True,
        )

    with watchlist_tab:
        render_domain_idea_review_table(
            domain_ideas_df,
            bucket="Watchlist",
            empty_message="لا توجد watchlist ideas حاليًا.",
            export_file_name="domain_watchlist.xlsx",
        )

    with rejected_tab:
        render_domain_idea_review_table(
            domain_ideas_df,
            bucket="Rejected",
            empty_message="لا توجد rejected ideas محفوظة بعد.",
            export_file_name="domain_rejected.xlsx",
        )

    with all_ideas_tab:
        render_domain_idea_review_table(
            domain_ideas_df,
            bucket="All",
            empty_message="لا توجد domain ideas محفوظة بعد. شغّل `generate_domain_ideas` أولًا.",
            export_file_name="domain_ideas.xlsx",
        )
