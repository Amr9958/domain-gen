"""Runtime helpers for env values and optional Streamlit secrets."""

from __future__ import annotations

import os

try:
    import streamlit as st
except ImportError:  # pragma: no cover - streamlit may be absent in non-UI contexts
    st = None


def get_runtime_secret(name: str, default: str = "", session_key: str = "") -> str:
    """Resolve a setting from Streamlit secrets, session state, then env."""
    if st is not None:
        try:
            secret_value = st.secrets.get(name, "")
            if isinstance(secret_value, str) and secret_value.strip():
                return secret_value.strip()
        except Exception:
            pass

        if session_key:
            session_value = st.session_state.get(session_key, "")
            if isinstance(session_value, str) and session_value.strip():
                return session_value.strip()

    return os.getenv(name, default).strip()


def get_runtime_value(name: str, default: str = "", session_key: str = "") -> str:
    """Resolve a non-secret runtime value from session state, env, then default."""
    if st is not None and session_key:
        session_value = st.session_state.get(session_key, "")
        if isinstance(session_value, str) and session_value.strip():
            return session_value.strip()
    return os.getenv(name, default).strip()
