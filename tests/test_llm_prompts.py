"""Tests for LLM prompt-building helpers."""

from __future__ import annotations

import unittest

from providers.llm import (
    _build_domain_generation_prompt,
    _choose_domain_generation_styles,
    _normalize_llm_domain_suggestions,
)


class LlmPromptTests(unittest.TestCase):
    def test_style_selection_adds_geo_only_for_explicit_geo_keywords(self) -> None:
        styles_without_geo = _choose_domain_generation_styles("Real Estate", ["roofing", "property"])
        styles_with_geo = _choose_domain_generation_styles("Real Estate", ["miami", "roofing"])

        self.assertNotIn("geo", styles_without_geo)
        self.assertIn("geo", styles_with_geo)
        self.assertIn("outbound", styles_with_geo)

    def test_build_domain_generation_prompt_contains_structured_json_schema(self) -> None:
        system, prompt = _build_domain_generation_prompt(
            niche="Tech & AI",
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
            niche="Tech & AI",
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
            niche="Real Estate",
            existing=[],
            selected_keywords=["property"],
            requested_styles=["auto"],
            geo_context="Saudi Arabia, Riyadh",
            count=6,
        )

        self.assertIn("Explicit geo context:", prompt)
        self.assertIn("saudi arabia, riyadh", prompt)
        self.assertIn("- geo:", prompt)

    def test_normalize_llm_domain_suggestions_accepts_strings_and_objects(self) -> None:
        normalized = _normalize_llm_domain_suggestions(
            [
                {"name": "LedgerMint.com", "style": "hybrid"},
                {"domain": "Voxera.ai", "category": "ai futuristic"},
                "SignalCore.io",
            ]
        )

        self.assertEqual(
            normalized,
            [
                {"name": "ledgermint", "method": "hybrid"},
                {"name": "voxera", "method": "ai_futuristic"},
                {"name": "signalcore", "method": "llm"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
