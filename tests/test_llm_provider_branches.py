"""Tests for LLM provider routing without external network calls."""

from __future__ import annotations

import pytest

import config.runtime as runtime_config
import providers.llm as llm


class FakeSidebar:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, str] = {"ai_provider": llm.OPENROUTER_PROVIDER}
        self.sidebar = FakeSidebar()


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(str(outcome))


class FakeOpenAIClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.chat = type("FakeChat", (), {})()
        self.chat.completions = FakeCompletions(outcomes)


class FakeOpenAIFactory:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.instances: list[FakeOpenAIClient] = []
        self.init_kwargs: list[dict[str, str]] = []

    def __call__(self, **kwargs) -> FakeOpenAIClient:
        self.init_kwargs.append(kwargs)
        client = FakeOpenAIClient(self.outcomes)
        self.instances.append(client)
        return client


@pytest.fixture()
def fake_streamlit(monkeypatch) -> FakeStreamlit:
    fake_st = FakeStreamlit()
    monkeypatch.setattr(llm, "st", fake_st)
    monkeypatch.setattr(runtime_config, "st", None)
    return fake_st


def test_openrouter_without_api_key_disables_llm(monkeypatch, fake_streamlit) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(llm, "OpenAI", lambda **_: pytest.fail("OpenAI client should not be created without a key"))

    result = llm.call_llm("ping")

    assert result == ""
    assert fake_streamlit.session_state["last_llm_status"] == "disabled"
    assert "OpenRouter" in fake_streamlit.session_state["last_llm_message"]


def test_openrouter_uses_openrouter_api_key_and_returns_primary_success(monkeypatch, fake_streamlit) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/test-model")
    factory = FakeOpenAIFactory(["{\"ok\": true}"])
    monkeypatch.setattr(llm, "OpenAI", factory)

    result = llm.call_llm("return json", system="system prompt", json_mode=True)

    assert result == "{\"ok\": true}"
    assert factory.init_kwargs == [
        {
            "api_key": "test-openrouter-key",
            "base_url": "https://openrouter.ai/api/v1",
        }
    ]
    call = factory.instances[0].chat.completions.calls[0]
    assert call["model"] == "openrouter/test-model"
    assert call["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "return json"},
    ]
    assert fake_streamlit.session_state["last_llm_status"] == "direct"
    assert fake_streamlit.session_state["last_llm_model_used"] == "openrouter/test-model"


def test_openrouter_falls_back_to_free_model_after_primary_failure(monkeypatch, fake_streamlit) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/paid-model")
    factory = FakeOpenAIFactory([RuntimeError("primary unavailable"), "fallback response"])
    monkeypatch.setattr(llm, "OpenAI", factory)

    result = llm.call_llm("ping")

    assert result == "fallback response"
    calls = factory.instances[0].chat.completions.calls
    assert [call["model"] for call in calls] == ["openrouter/paid-model", llm.OPENROUTER_FREE_MODEL]
    assert fake_streamlit.sidebar.warnings
    assert fake_streamlit.session_state["last_llm_status"] == "fallback_free"
    assert fake_streamlit.session_state["last_llm_model_used"] == llm.OPENROUTER_FREE_MODEL


def test_openrouter_reports_internal_only_after_primary_and_fallback_failure(monkeypatch, fake_streamlit) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/paid-model")
    factory = FakeOpenAIFactory([RuntimeError("primary unavailable"), RuntimeError("fallback unavailable")])
    monkeypatch.setattr(llm, "OpenAI", factory)

    result = llm.call_llm("ping")

    assert result == ""
    assert fake_streamlit.sidebar.errors
    assert fake_streamlit.session_state["last_llm_status"] == "internal_only"
    assert fake_streamlit.session_state["last_llm_model_used"] == ""
