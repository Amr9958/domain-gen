"""Session-state initialization helpers."""

from __future__ import annotations

import streamlit as st

from utils.word_banks import load_word_banks


SESSION_DEFAULTS = {
    "history": [],
    "favorites": [],
    "last_results": [],
    "last_categories": {},
    "show_results": False,
    "generating": False,
}


def initialize_session_state() -> None:
    """Populate required Streamlit session keys if they are missing."""
    if "word_banks" not in st.session_state:
        st.session_state.word_banks = load_word_banks()

    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default.copy() if isinstance(default, (list, dict)) else default


def reset_all_app_data() -> None:
    """Clear all Streamlit session keys for a fresh app state."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
