"""Streamlit page for reviewing watchlist domain ideas."""

from __future__ import annotations

import streamlit as st

from repositories.signals import get_signal_repository
from utils.page_setup import bootstrap_page
from utils.trend_dashboard import prepare_domain_ideas_dataframe, render_domain_idea_review_table


bootstrap_page("Watchlist Review")

st.title("👀 Watchlist Review")
st.caption("مراجعة الأفكار التي تستحق المراقبة ولم تصل بعد إلى shortlist نهائية.")

repository = get_signal_repository()
domain_ideas_df = prepare_domain_ideas_dataframe(repository.list_domain_ideas())

render_domain_idea_review_table(
    domain_ideas_df,
    bucket="Watchlist",
    empty_message="لا توجد watchlist ideas حاليًا.",
    export_file_name="domain_watchlist.xlsx",
)
