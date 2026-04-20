"""Streamlit page for reviewing shortlist-ready domain ideas."""

from __future__ import annotations

import streamlit as st

from repositories.signals import get_signal_repository
from utils.page_setup import bootstrap_page
from utils.trend_dashboard import prepare_domain_ideas_dataframe, render_domain_idea_review_table


bootstrap_page("Shortlist Review")

st.title("🏁 Shortlist Review")
st.caption("مراجعة أقوى domain ideas مع إمكانية الإضافة للـ Portfolio وAI refinement الاختياري.")

repository = get_signal_repository()
domain_ideas_df = prepare_domain_ideas_dataframe(repository.list_domain_ideas())

render_domain_idea_review_table(
    domain_ideas_df,
    bucket="Shortlist",
    empty_message="لا توجد shortlist ideas بعد. شغّل `generate_domain_ideas` أولًا.",
    export_file_name="domain_shortlist.xlsx",
    allow_portfolio_add=True,
    allow_ai_refinement=True,
)
