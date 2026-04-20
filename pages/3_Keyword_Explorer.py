"""Streamlit page for exploring keyword intelligence output."""

from __future__ import annotations

import streamlit as st

from repositories.signals import get_signal_repository
from utils.export import dataframe_to_excel_bytes
from utils.page_setup import bootstrap_page
from utils.trend_dashboard import prepare_keyword_insights_dataframe, render_keyword_refinement_panel


bootstrap_page("Keyword Explorer")

st.title("🔎 Keyword Explorer")
st.caption("فلاتر وتحليل سريع للـ keyword intelligence الناتجة من themes.")

repository = get_signal_repository()
keywords_df = prepare_keyword_insights_dataframe(repository.list_keywords())

if keywords_df.empty:
    st.info("لا توجد keyword insights محفوظة بعد. شغّل `process_signals` أولًا.")
else:
    theme_options = ["All"] + sorted(keywords_df["Theme"].dropna().astype(str).unique().tolist())
    theme_filter = st.selectbox("Theme Filter", theme_options, index=0)

    niche_options = ["All"] + sorted(keywords_df["Niche"].dropna().astype(str).unique().tolist())
    niche_filter = st.selectbox("Niche Filter", niche_options, index=0)

    type_options = ["All"] + sorted(keywords_df["Type"].dropna().astype(str).unique().tolist())
    type_filter = st.selectbox("Keyword Type Filter", type_options, index=0)

    filtered_keywords_df = keywords_df.copy()
    if theme_filter != "All":
        filtered_keywords_df = filtered_keywords_df[filtered_keywords_df["Theme"] == theme_filter]
    if niche_filter != "All":
        filtered_keywords_df = filtered_keywords_df[filtered_keywords_df["Niche"] == niche_filter]
    if type_filter != "All":
        filtered_keywords_df = filtered_keywords_df[filtered_keywords_df["Type"] == type_filter]

    if filtered_keywords_df.empty:
        st.info("لا توجد keyword insights مطابقة للفلاتر الحالية.")
    else:
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Keywords", len(filtered_keywords_df))
        metric_col2.metric("Themes", filtered_keywords_df["Theme"].nunique())
        metric_col3.metric("Avg Commercial", f"{filtered_keywords_df['Commercial'].mean():.2f}")

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("Keyword Type Distribution")
            st.bar_chart(filtered_keywords_df["Type"].value_counts())
        with chart_col2:
            st.caption("Theme Distribution")
            st.bar_chart(filtered_keywords_df["Theme"].value_counts().head(10))

        st.dataframe(filtered_keywords_df, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Export Filtered Keywords",
            data=dataframe_to_excel_bytes(filtered_keywords_df, sheet_name="Keywords"),
            file_name="keyword_explorer.xlsx",
        )
        render_keyword_refinement_panel(filtered_keywords_df, key_prefix="keyword_explorer")
