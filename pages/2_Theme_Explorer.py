"""Streamlit page for exploring consolidated themes and their downstream effects."""

from __future__ import annotations

import streamlit as st

from repositories.signals import get_signal_repository
from utils.export import dataframe_to_excel_bytes
from utils.page_setup import bootstrap_page
from utils.trend_dashboard import (
    prepare_domain_ideas_dataframe,
    prepare_keyword_insights_dataframe,
    prepare_themes_dataframe,
    render_theme_refinement_panel,
)


bootstrap_page("Theme Explorer")

st.title("🧩 Theme Explorer")
st.caption("استكشاف themes المجمعة وما يرتبط بها من keywords وdomain ideas.")

repository = get_signal_repository()
themes_df = prepare_themes_dataframe(repository.list_themes())
keywords_df = prepare_keyword_insights_dataframe(repository.list_keywords())
domain_ideas_df = prepare_domain_ideas_dataframe(repository.list_domain_ideas())

if themes_df.empty:
    st.info("لا توجد themes محفوظة بعد. شغّل `process_signals` أولًا.")
else:
    classification_options = ["All"] + sorted(themes_df["Classification"].dropna().astype(str).unique().tolist())
    classification_filter = st.selectbox("Classification Filter", classification_options, index=0)

    source_type_terms: set[str] = set()
    for raw_types in themes_df["Source Types"].dropna().astype(str).tolist():
        source_type_terms.update(part.strip() for part in raw_types.split(",") if part.strip())
    source_type_options = ["All"] + sorted(source_type_terms)
    source_type_filter = st.selectbox("Source Type Filter", source_type_options, index=0)

    filtered_themes_df = themes_df.copy()
    if classification_filter != "All":
        filtered_themes_df = filtered_themes_df[filtered_themes_df["Classification"] == classification_filter]
    if source_type_filter != "All":
        filtered_themes_df = filtered_themes_df[
            filtered_themes_df["Source Types"].str.contains(source_type_filter, case=False, na=False)
        ]

    if filtered_themes_df.empty:
        st.info("لا توجد themes مطابقة للفلاتر الحالية.")
    else:
        selected_theme = st.selectbox("اختر Theme", filtered_themes_df["Theme"].tolist())
        selected_theme_row = filtered_themes_df[filtered_themes_df["Theme"] == selected_theme].iloc[0]

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Momentum", selected_theme_row["Momentum"])
        metric_col2.metric("Signals", selected_theme_row["Signals"])
        metric_col3.metric("Classification", selected_theme_row["Classification"])

        st.caption(selected_theme_row["Description"])
        st.code(
            "\n".join(
                [
                    f"Sources: {selected_theme_row['Sources'] or '(none)'}",
                    f"Source Breakdown: {selected_theme_row['Source Breakdown'] or '(none)'}",
                    f"Source Types: {selected_theme_row['Source Types'] or '(none)'}",
                    f"Source Tags: {selected_theme_row['Source Tags'] or '(none)'}",
                    f"Source Entities: {selected_theme_row['Source Entities'] or '(none)'}",
                    f"Cluster Keys: {selected_theme_row['Cluster Keys'] or '(none)'}",
                    f"Reason Highlights: {selected_theme_row['Reason Highlights'] or '(none)'}",
                    f"Evidence Titles: {selected_theme_row['Evidence Titles'] or '(none)'}",
                    f"Related Terms: {selected_theme_row['Related Terms'] or '(none)'}",
                ]
            ),
            language="text",
        )

        related_keywords_df = keywords_df[keywords_df["Theme"] == selected_theme] if not keywords_df.empty else keywords_df
        related_ideas_df = domain_ideas_df[domain_ideas_df["Theme"] == selected_theme] if not domain_ideas_df.empty else domain_ideas_df

        tab1, tab2, tab3 = st.tabs(["Theme Table", "Related Keywords", "Related Ideas"])

        with tab1:
            st.dataframe(filtered_themes_df, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Export Filtered Themes",
                data=dataframe_to_excel_bytes(filtered_themes_df, sheet_name="Themes"),
                file_name="theme_explorer_themes.xlsx",
            )
            render_theme_refinement_panel(filtered_themes_df, key_prefix="theme_explorer")

        with tab2:
            if related_keywords_df.empty:
                st.info("لا توجد keyword insights مرتبطة بهذه الـ theme.")
            else:
                st.dataframe(related_keywords_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "📥 Export Related Keywords",
                    data=dataframe_to_excel_bytes(related_keywords_df, sheet_name="Keywords"),
                    file_name="theme_explorer_keywords.xlsx",
                )

        with tab3:
            if related_ideas_df.empty:
                st.info("لا توجد domain ideas مرتبطة بهذه الـ theme.")
            else:
                st.dataframe(related_ideas_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "📥 Export Related Ideas",
                    data=dataframe_to_excel_bytes(related_ideas_df, sheet_name="Ideas"),
                    file_name="theme_explorer_ideas.xlsx",
                )
