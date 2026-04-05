"""LLM provider integrations used by the Streamlit app."""

from __future__ import annotations

import json

import streamlit as st
from google import genai
from openai import OpenAI

from constants import DEFAULT_AI_PROVIDER


XAI_PROVIDER = "xAI (Grok)"
GEMINI_PROVIDER = "Google Gemini"
OPENROUTER_PROVIDER = "OpenRouter"


def call_llm(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """Unified LLM caller for the currently selected provider."""
    provider = st.session_state.get("ai_provider", DEFAULT_AI_PROVIDER)

    if provider == XAI_PROVIDER:
        api_key = st.secrets.get("XAI_API_KEY", st.session_state.get("xai_key", "")).strip()
        model = st.secrets.get("XAI_MODEL", st.session_state.get("xai_model", "grok-3-mini")).strip()
        if not api_key:
            return ""
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            kwargs = {"messages": messages, "model": model, "max_tokens": 500}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as exc:
            st.sidebar.error(f"xAI Error: {exc}")
            return ""

    if provider == GEMINI_PROVIDER:
        api_key = st.secrets.get("GEMINI_API_KEY", st.session_state.get("gemini_key", "")).strip()
        model = st.secrets.get("GEMINI_MODEL", st.session_state.get("gemini_model", "gemini-2.0-flash")).strip()
        if not api_key:
            return ""
        try:
            client = genai.Client(api_key=api_key)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = client.models.generate_content(model=model, contents=full_prompt)
            return response.text.strip()
        except Exception as exc:
            st.sidebar.error(f"Gemini Error: {exc}")
            return ""

    if provider == OPENROUTER_PROVIDER:
        api_key = st.secrets.get("OPENROUTER_API_KEY", st.session_state.get("or_key", "")).strip()
        model = st.secrets.get(
            "OPENROUTER_MODEL",
            st.session_state.get("or_model", "google/gemini-2.0-flash-001"),
        ).strip()
        if not api_key:
            return ""
        try:
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(messages=messages, model=model, max_tokens=500)
            return response.choices[0].message.content.strip()
        except Exception as exc:
            st.sidebar.error(f"OpenRouter Error: {exc}")
            return ""

    return ""


def parse_json_response(text: str, key: str) -> list:
    """Safely parse JSON from an LLM response, including fenced code blocks."""
    if not text:
        return []

    try:
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        data = json.loads(text)
        return data.get(key, list(data.values())[0] if data else [])
    except Exception:
        return []


def llm_creative_boost(niche: str, existing: list[str], count: int = 8) -> list[str]:
    """Ask the configured LLM for additional brandable domain ideas."""
    prompt = (
        f"Generate {count} unique, brandable, 1-word or 2-word domain names for the '{niche}' niche. "
        f"Avoid: {existing[:20]}. Focus on short (5-12 chars), memorable names. "
        f"Return ONLY a JSON object: {{\"domains\": [\"name1\", \"name2\", ...]}}"
    )
    text = call_llm(prompt, json_mode=True)
    return [name.lower().replace(" ", "") for name in parse_json_response(text, "domains")]


def ai_suggest_words(niche: str, category: str, current_words: list[str]) -> list[str]:
    """Ask the configured LLM for extra word-bank suggestions."""
    prompt = (
        f"Suggest 10 new high-quality, brandable single-word domain concepts for the category '{category}' "
        f"in the '{niche}' niche. Return ONLY absolute single words, max 15 chars each. "
        f"Return ONLY a JSON object: {{\"words\": [\"word1\", \"word2\", ...]}}"
    )
    system = "You are a professional domain name brand expert."
    text = call_llm(prompt, system=system, json_mode=True)
    raw_words = parse_json_response(text, "words")
    return [
        word.replace(" ", "").lower().strip()
        for word in raw_words
        if word and len(word.replace(" ", "")) <= 20 and word not in current_words
    ]


def test_connection(provider_name: str, api_key: str, model: str) -> tuple[bool, str]:
    """Run a minimal provider test using the current app routing logic."""
    _ = api_key, model
    previous_provider = st.session_state.get("ai_provider")
    st.session_state["ai_provider"] = provider_name
    result = call_llm("ping", json_mode=False)
    st.session_state["ai_provider"] = previous_provider
    if result:
        return True, f"✅ تم الربط بـ {model} بنجاح!"
    return False, "❌ فشل الربط — تأكد من الـ API Key والموديل"
