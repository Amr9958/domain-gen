"""Tests for LLM prompt-building helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from generator import _resolve_generation_styles
from providers.llm import (
    _build_domain_generation_prompt,
    _normalize_llm_domain_suggestions,
    ai_suggest_keywords_from_topic,
    ai_suggest_words,
    ai_refine_shortlist_domains,
    parse_json_response,
)


class LlmPromptTests(unittest.TestCase):
    def test_style_selection_adds_geo_only_for_explicit_geo_keywords(self) -> None:
        styles_without_geo = _resolve_generation_styles("Real Estate & Property", ["roofing", "property"], [], ["auto"])
        styles_with_geo = _resolve_generation_styles("Real Estate & Property", ["miami", "roofing"], [], ["auto"])

        self.assertNotIn("geo", styles_without_geo)
        self.assertIn("geo", styles_with_geo)
        self.assertIn("compound", styles_with_geo)

    def test_build_domain_generation_prompt_contains_structured_json_schema(self) -> None:
        system, prompt = _build_domain_generation_prompt(
            niche="Tech & SaaS",
            existing=["agentdock", "voxmesh"],
            selected_keywords=["voice", "agent", "automation"],
            count=10,
        )

        self.assertIn("world-class domain strategist", system)
        self.assertIn("Generate 10 unique domain concepts", prompt)
        self.assertIn('"domains"', prompt)
        self.assertIn('"style"', prompt)
        self.assertIn("avoid these existing names: agentdock, voxmesh", prompt)

    def test_build_domain_generation_prompt_respects_explicit_styles(self) -> None:
        _, prompt = _build_domain_generation_prompt(
            niche="Tech & SaaS",
            existing=[],
            selected_keywords=["voice", "agent"],
            requested_styles=["brandable", "short"],
            count=6,
        )

        self.assertIn("- brandable:", prompt)
        self.assertIn("- short:", prompt)
        self.assertNotIn("- exact:", prompt)
        self.assertNotIn("- geo:", prompt)

    def test_build_domain_generation_prompt_includes_explicit_geo_context_for_auto(self) -> None:
        _, prompt = _build_domain_generation_prompt(
            niche="Real Estate & Property",
            existing=[],
            selected_keywords=["property"],
            requested_styles=["auto"],
            geo_context="Saudi Arabia, Riyadh",
            count=6,
        )

        self.assertIn("Explicit geo context:", prompt)
        self.assertIn("saudi arabia, riyadh", prompt)
        self.assertIn("- geo:", prompt)

    def test_build_domain_generation_prompt_requires_visible_mcp_keyword(self) -> None:
        _, prompt = _build_domain_generation_prompt(
            niche="Tech & SaaS",
            existing=[],
            selected_keywords=["mcp", "agent", "workflow"],
            requested_styles=["auto"],
            count=8,
        )

        self.assertIn("Every returned domain name must visibly include `mcp`", prompt)

    def test_normalize_llm_domain_suggestions_accepts_strings_and_objects(self) -> None:
        normalized = _normalize_llm_domain_suggestions(
            [
                {"name": "LedgerMint.com", "style": "compound"},
                {"domain": "Voxera.ai", "category": "ai futuristic"},
                {"domain": "LaunchFlow.com", "category": "action"},
                "SignalCore.io",
            ]
        )

        self.assertEqual(
            normalized,
            [
                {"name": "ledgermint", "method": "compound"},
                {"name": "voxera", "method": "invented"},
                {"name": "launchflow", "method": "exact"},
                {"name": "signalcore", "method": "llm"},
            ],
        )

    def test_normalize_llm_domain_suggestions_rejects_names_missing_required_keyword(self) -> None:
        normalized = _normalize_llm_domain_suggestions(
            [
                {"name": "MCPAlo.com", "style": "invented"},
                {"domain": "CleanSignal.com", "category": "brandable"},
                {"domain": "MCPOra.ai", "category": "brandable"},
            ],
            required_keyword="mcp",
        )

        self.assertEqual(
            normalized,
            [
                {"name": "mcpalo", "method": "invented"},
                {"name": "mcpora", "method": "brandable"},
            ],
        )

    def test_parse_json_response_handles_fenced_json_and_fallback_key(self) -> None:
        fenced = '```json\n{"keywords": ["agent", "workflow"]}\n```'
        fallback = '{"items": ["ledger", "vault"]}'

        self.assertEqual(parse_json_response(fenced, "keywords"), ["agent", "workflow"])
        self.assertEqual(parse_json_response(fallback, "keywords"), ["ledger", "vault"])
        self.assertEqual(parse_json_response("not json", "keywords"), [])

    @patch("providers.llm.call_llm")
    def test_ai_suggest_words_filters_duplicates_and_long_items(self, mocked_call_llm) -> None:
        mocked_call_llm.return_value = '{"words": ["Nexa Flow", "existing", "averyveryveryverylongword"]}'

        words = ai_suggest_words("Tech & SaaS", "brandable", ["existing"])

        self.assertEqual(words, ["nexaflow"])

    @patch("providers.llm.call_llm")
    def test_ai_suggest_keywords_from_topic_normalizes_and_dedupes_existing(self, mocked_call_llm) -> None:
        mocked_call_llm.return_value = '{"keywords": ["Agent Ops", "ai", "existing", "averyveryveryverylongkeyword"]}'

        keywords = ai_suggest_keywords_from_topic(
            "agent workflow automation",
            ["Tech & SaaS"],
            existing_keywords=["existing"],
            count=4,
        )

        self.assertEqual(keywords, ["agentops", "ai"])

    @patch("providers.llm.call_llm")
    def test_shortlist_refinement_outputs_include_trace_refs(self, mocked_call_llm) -> None:
        mocked_call_llm.return_value = (
            '{"refined_domains": [{"domain": "atlasai.com", "investor_score": 82, '
            '"verdict": "hold_watch", "priority": "high", "buyer_angle": "AI ops", '
            '"why_good": "Clear buyer fit", "risk_summary": "No obvious issue"}]}'
        )

        refined = ai_refine_shortlist_domains(
            [
                {
                    "Domain": "atlasai.com",
                    "Theme": "Agent Ops",
                    "Keyword": "agent",
                    "Niche": "Tech & SaaS",
                }
            ]
        )

        self.assertEqual(len(refined), 1)
        self.assertEqual(refined[0]["provenance"], "llm_refinement")
        self.assertEqual(refined[0]["input_ref"]["domain"], "atlasai.com")
        self.assertEqual(refined[0]["input_ref"]["theme"], "Agent Ops")


if __name__ == "__main__":
    unittest.main()
