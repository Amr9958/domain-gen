"""Optional live smoke test for the OpenRouter generation route."""

from __future__ import annotations

import os

import pytest

import config.runtime as runtime_config
import providers.llm as llm


class _LiveSmokeSidebar:
    def warning(self, _message: str) -> None:
        return None

    def error(self, _message: str) -> None:
        return None


class _LiveSmokeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, str] = {"ai_provider": llm.OPENROUTER_PROVIDER}
        self.sidebar = _LiveSmokeSidebar()


@pytest.mark.live_openrouter
def test_live_openrouter_can_generate_mcp_domains_when_enabled(monkeypatch) -> None:
    if os.getenv("RUN_LIVE_OPENROUTER") != "1":
        pytest.skip("Set RUN_LIVE_OPENROUTER=1 to run the live OpenRouter smoke test.")

    api_key = runtime_config.get_runtime_secret("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY is not configured in Streamlit secrets or env.")

    model = runtime_config.get_runtime_value("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    monkeypatch.setenv("OPENROUTER_API_KEY", api_key)
    monkeypatch.setenv("OPENROUTER_MODEL", model)
    monkeypatch.setattr(llm, "st", _LiveSmokeStreamlit())
    monkeypatch.setattr(runtime_config, "st", None)

    suggestions = llm.llm_creative_boost(
        niche="Tech & SaaS",
        existing=[],
        selected_keywords=["mcp"],
        requested_styles=["brandable", "compound"],
        count=3,
    )

    assert suggestions
    assert all("name" in suggestion and suggestion["name"] for suggestion in suggestions)
    assert all("mcp" in str(suggestion["name"]) for suggestion in suggestions)
