"""Streamlit page for trend pipeline overview and controls."""

from __future__ import annotations

import streamlit as st

from integrations import get_supabase_manager
from jobs import run_domain_idea_job, run_ingest_job, run_processing_job
from repositories.signals import get_signal_repository
from utils.export import dataframe_to_excel_bytes
from utils.page_setup import bootstrap_page
from utils.trend_dashboard import (
    prepare_domain_ideas_dataframe,
    prepare_keyword_insights_dataframe,
    prepare_themes_dataframe,
)


bootstrap_page("Trend Overview")

st.title("🧭 Trend Overview")
st.caption("لوحة سريعة لتشغيل الـ pipeline ومراجعة أهم النتائج الحالية عبر الصفحات الجديدة.")

supabase_health = get_supabase_manager().health()
if supabase_health.enabled:
    st.caption(f"Supabase status: {supabase_health.reason}")

action_col1, action_col2, action_col3, action_col4 = st.columns(4)

if action_col1.button("⬇️ Run Ingest", help="Collect fresh raw signals from configured sources."):
    with st.spinner("Running ingest_signals..."):
        ingest_summary = run_ingest_job()
    st.success("تم تشغيل ingest_signals بنجاح.")
    st.json(ingest_summary)

if action_col2.button("⚙️ Run Process", help="Clean, classify, and extract themes/keywords."):
    with st.spinner("Running process_signals..."):
        process_summary = run_processing_job()
    st.success("تم تشغيل process_signals بنجاح.")
    st.json(process_summary)

if action_col3.button("💡 Generate Ideas", help="Generate scored domain ideas from stored themes and keywords."):
    with st.spinner("Running generate_domain_ideas..."):
        idea_summary = run_domain_idea_job()
    st.success("تم تشغيل generate_domain_ideas بنجاح.")
    st.json(idea_summary)

if action_col4.button("🔄 Run Full Pipeline", help="Run ingest, process, then domain idea generation."):
    with st.spinner("Running full trend pipeline..."):
        ingest_summary = run_ingest_job()
        process_summary = run_processing_job()
        idea_summary = run_domain_idea_job()
    st.success("تم تشغيل المسار الكامل بنجاح.")
    st.json({"ingest": ingest_summary, "process": process_summary, "domain_ideas": idea_summary})

repository = get_signal_repository()
themes = repository.list_themes()
keywords = repository.list_keywords()
domain_ideas = repository.list_domain_ideas()

themes_df = prepare_themes_dataframe(themes)
keywords_df = prepare_keyword_insights_dataframe(keywords)
domain_ideas_df = prepare_domain_ideas_dataframe(domain_ideas)

shortlist_count = int((domain_ideas_df["Bucket"] == "Shortlist").sum()) if not domain_ideas_df.empty else 0
watchlist_count = int((domain_ideas_df["Bucket"] == "Watchlist").sum()) if not domain_ideas_df.empty else 0
rejected_count = int((domain_ideas_df["Bucket"] == "Rejected").sum()) if not domain_ideas_df.empty else 0

metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
metric_col1.metric("Themes", len(themes))
metric_col2.metric("Keywords", len(keywords))
metric_col3.metric("Shortlist", shortlist_count)
metric_col4.metric("Watchlist", watchlist_count)
metric_col5.metric("Rejected", rejected_count)

if domain_ideas_df.empty:
    st.info("لا توجد domain ideas محفوظة بعد. شغّل `generate_domain_ideas` من الأعلى.")
else:
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.caption("Review Bucket Distribution")
        st.bar_chart(domain_ideas_df["Bucket"].value_counts())
    with chart_col2:
        st.caption("Top Themes In Review Queue")
        st.bar_chart(domain_ideas_df["Theme"].value_counts().head(10))

overview_col1, overview_col2 = st.columns(2)

with overview_col1:
    st.subheader("Top Themes")
    if themes_df.empty:
        st.info("لا توجد themes بعد.")
    else:
        top_themes_df = themes_df.head(12)
        st.dataframe(top_themes_df, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Export Themes Snapshot",
            data=dataframe_to_excel_bytes(top_themes_df, sheet_name="TopThemes"),
            file_name="trend_overview_themes.xlsx",
        )

with overview_col2:
    st.subheader("Top Shortlist Ideas")
    shortlist_df = domain_ideas_df[domain_ideas_df["Bucket"] == "Shortlist"] if not domain_ideas_df.empty else domain_ideas_df
    if shortlist_df.empty:
        st.info("لا توجد shortlist ideas حاليًا.")
    else:
        top_shortlist_df = shortlist_df.head(12)
        st.dataframe(top_shortlist_df, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Export Shortlist Snapshot",
            data=dataframe_to_excel_bytes(top_shortlist_df, sheet_name="Shortlist"),
            file_name="trend_overview_shortlist.xlsx",
        )

with st.expander("Keyword Snapshot", expanded=False):
    if keywords_df.empty:
        st.info("لا توجد keyword insights محفوظة بعد.")
    else:
        st.dataframe(keywords_df.head(20), use_container_width=True, hide_index=True)
