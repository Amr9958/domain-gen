"""Common Streamlit page bootstrap helpers."""

from __future__ import annotations

import streamlit as st

from constants import APP_ICON, APP_LAYOUT, APP_TITLE
from core.logging import configure_logging
from storage import init_db
from utils.session import initialize_session_state


def bootstrap_page(page_title: str) -> None:
    """Initialize a standalone Streamlit page with shared app defaults."""
    configure_logging()
    st.set_page_config(page_title=f"{APP_TITLE} · {page_title}", page_icon=APP_ICON, layout=APP_LAYOUT)
    init_db()
    initialize_session_state()
