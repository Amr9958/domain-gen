"""Streamlit page for reviewing rejected domain ideas and risk notes."""

from __future__ import annotations

import streamlit as st

from repositories.signals import get_signal_repository
from utils.page_setup import bootstrap_page
from utils.trend_dashboard import prepare_domain_ideas_dataframe, render_domain_idea_review_table


bootstrap_page("Rejected Ideas")

st.title("🛑 Rejected Ideas")
st.caption("مراجعة الأفكار المرفوضة وأسباب الرفض والمخاطر المرتبطة بها.")

repository = get_signal_repository()
domain_ideas_df = prepare_domain_ideas_dataframe(repository.list_domain_ideas())

render_domain_idea_review_table(
    domain_ideas_df,
    bucket="Rejected",
    empty_message="لا توجد rejected ideas محفوظة بعد.",
    export_file_name="domain_rejected.xlsx",
)
