"""Tests for the offline domain generator fallback."""

from __future__ import annotations

import unittest

from generator import generate_domains


TEST_WORD_BANKS = {
    "abstract": ["nexus", "nova", "prime", "vector"],
    "power": ["forge", "signal", "swift", "vault"],
    "tech": ["agent", "cloud", "data", "mesh", "ops", "stack", "voice"],
    "finance": ["audit", "fund", "ledger", "risk", "tax"],
    "creative": ["canvas", "craft", "design", "pixel"],
    "short_prefixes": ["clear", "neo", "nex", "smart", "vox", "zen"],
}


class OfflineGeneratorTests(unittest.TestCase):
    def test_generate_domains_offline_is_deterministic_and_multi_style(self) -> None:
        first = generate_domains(
            niche="Tech & AI",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="voice, agent, automation",
            num_per_tier=6,
        )
        second = generate_domains(
            niche="Tech & AI",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="voice, agent, automation",
            num_per_tier=6,
        )

        self.assertEqual(first, second)
        self.assertGreater(len(first), 12)

        methods = {str(candidate["method"]) for candidate in first}
        self.assertIn("exact", methods)
        self.assertIn("hybrid", methods)
        self.assertIn("brandable", methods)
        self.assertTrue({"ai", "ai_model"} & methods)
        self.assertIn("short", methods)

    def test_generate_domains_offline_supports_geo_when_geo_keyword_exists(self) -> None:
        candidates = generate_domains(
            niche="Finance & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="dubai, tax",
            num_per_tier=6,
        )

        self.assertTrue(
            any(
                str(candidate["method"]).startswith("geo") and str(candidate["name"]).startswith("dubai")
                for candidate in candidates
            )
        )

    def test_generate_domains_offline_supports_explicit_geo_context(self) -> None:
        candidates = generate_domains(
            niche="Finance & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            requested_styles=["geo"],
            keywords_str="tax",
            geo_context="Dubai",
            num_per_tier=6,
        )

        self.assertTrue(
            any(
                str(candidate["method"]).startswith("geo") and str(candidate["name"]).startswith("dubai")
                for candidate in candidates
            )
        )

    def test_generate_domains_offline_can_generate_without_keywords(self) -> None:
        candidates = generate_domains(
            niche="Real Estate",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="",
            num_per_tier=5,
        )

        self.assertGreater(len(candidates), 8)
        self.assertTrue(any(str(candidate["method"]) == "hybrid" for candidate in candidates))

    def test_generate_domains_respects_explicit_generation_style_selection(self) -> None:
        candidates = generate_domains(
            niche="Tech & AI",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            requested_styles=["brandable"],
            keywords_str="voice, agent, automation",
            num_per_tier=6,
        )

        methods = {str(candidate["method"]) for candidate in candidates}
        self.assertTrue(methods)
        self.assertEqual(methods, {"brandable"})


if __name__ == "__main__":
    unittest.main()
