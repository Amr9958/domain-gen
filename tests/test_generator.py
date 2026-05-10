"""Tests for the offline domain generator fallback."""

from __future__ import annotations

import unittest
from collections import Counter

from generator import _diversity_filter, _is_pronounceable, _normalize_requested_styles, _style_bucket, generate_domains


TEST_WORD_BANKS = {
    "abstract": ["nexus", "nova", "prime", "vector"],
    "power": ["forge", "signal", "swift", "vault"],
    "tech": ["agent", "cloud", "data", "mesh", "ops", "stack", "voice"],
    "finance": ["audit", "fund", "ledger", "risk", "tax"],
    "common_modifiers": ["flow", "forge", "hub", "labs", "mesh", "stack"],
    "brandable_fragments": ["canvas", "craft", "nexa", "pixel"],
    "property": ["estate", "home", "lease", "property", "realty", "roof"],
    "short_prefixes": ["clear", "neo", "nex", "smart", "vox", "zen"],
}


class OfflineGeneratorTests(unittest.TestCase):
    def test_generate_domains_offline_is_deterministic_and_multi_style(self) -> None:
        first = generate_domains(
            niche="Tech & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="voice, agent, automation",
            num_per_tier=6,
        )
        second = generate_domains(
            niche="Tech & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="voice, agent, automation",
            num_per_tier=6,
        )

        self.assertEqual(first, second)
        self.assertGreater(len(first), 12)

        methods = {str(candidate["method"]) for candidate in first}
        self.assertIn("exact", methods)
        self.assertIn("compound", methods)
        self.assertIn("brandable", methods)
        self.assertIn("invented", methods)
        self.assertIn("short", methods)

    def test_generate_domains_offline_supports_geo_when_geo_keyword_exists(self) -> None:
        candidates = generate_domains(
            niche="Finance & Fintech",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="dubai, tax",
            num_per_tier=6,
        )

        geo_candidates = [
            candidate["name"]
            for candidate in candidates
            if str(candidate["method"]).startswith("geo") and str(candidate["name"]).startswith("dubai")
        ]
        self.assertTrue(geo_candidates, f"Expected Dubai geo candidates, got {candidates!r}")

    def test_generate_domains_offline_supports_explicit_geo_context(self) -> None:
        candidates = generate_domains(
            niche="Finance & Fintech",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            requested_styles=["geo"],
            keywords_str="tax",
            geo_context="Dubai",
            num_per_tier=6,
        )

        geo_candidates = [
            candidate["name"]
            for candidate in candidates
            if str(candidate["method"]).startswith("geo") and str(candidate["name"]).startswith("dubai")
        ]
        self.assertTrue(geo_candidates, f"Expected explicit Dubai geo candidates, got {candidates!r}")

    def test_generate_domains_offline_can_generate_without_keywords(self) -> None:
        candidates = generate_domains(
            niche="Real Estate & Property",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="",
            num_per_tier=5,
        )

        self.assertGreater(len(candidates), 8)
        self.assertTrue(any(str(candidate["method"]).startswith("compound") for candidate in candidates))

    def test_generate_domains_respects_explicit_generation_style_selection(self) -> None:
        candidates = generate_domains(
            niche="Tech & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            requested_styles=["brandable"],
            keywords_str="voice, agent, automation",
            num_per_tier=6,
        )

        methods = {str(candidate["method"]) for candidate in candidates}
        style_buckets = {_style_bucket(method) for method in methods}
        self.assertTrue(methods, f"Expected brandable candidates, got {candidates!r}")
        self.assertEqual(style_buckets, {"brandable"}, f"Unexpected methods for brandable-only generation: {methods}")

    def test_legacy_generation_style_aliases_resolve_to_current_styles(self) -> None:
        self.assertEqual(
            _normalize_requested_styles(["hybrid", "ai_futuristic", "outbound"]),
            ["compound", "invented", "exact"],
        )

    def test_diversity_filter_caps_repeated_roots(self) -> None:
        candidates = [
            {"name": "agentflow", "method": "compound", "source_name": "agent", "is_transformed": True},
            {"name": "agentlabs", "method": "compound", "source_name": "agent", "is_transformed": True},
            {"name": "agentmesh", "method": "compound", "source_name": "agent", "is_transformed": True},
            {"name": "agenthub", "method": "compound", "source_name": "agent", "is_transformed": True},
            {"name": "datapad", "method": "compound", "source_name": "data", "is_transformed": True},
        ]

        filtered = _diversity_filter(candidates, max_per_root=3)
        roots = Counter(str(candidate["name"])[:4] for candidate in filtered)

        self.assertLessEqual(roots["agen"], 3)
        self.assertEqual(roots["data"], 1)

    def test_is_pronounceable_rejects_harsh_generated_names(self) -> None:
        self.assertTrue(_is_pronounceable("vexa"))
        self.assertTrue(_is_pronounceable("nelo"))
        self.assertTrue(_is_pronounceable("zura"))
        self.assertFalse(_is_pronounceable("strkly"))
        self.assertFalse(_is_pronounceable("aeiobox"))

    def test_generate_domains_balances_roots_and_styles_in_auto_mode(self) -> None:
        candidates = generate_domains(
            niche="Tech & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            keywords_str="agentic, workflow, data",
            num_per_tier=15,
        )

        roots = Counter(str(candidate["name"])[:4] for candidate in candidates)
        styles = Counter(_style_bucket(str(candidate["method"])) for candidate in candidates)

        self.assertTrue(candidates)
        self.assertLessEqual(max(roots.values()), 6)  # limit is max_per_root (3) + 3 for user keywords
        self.assertGreaterEqual(len(styles), 4)

    def test_short_and_invented_candidates_are_pronounceable(self) -> None:
        candidates = generate_domains(
            niche="Tech & SaaS",
            use_llm=False,
            word_banks=TEST_WORD_BANKS,
            requested_styles=["short", "invented"],
            keywords_str="agent, workflow, data",
            num_per_tier=12,
        )
        generated = [
            candidate
            for candidate in candidates
            if str(candidate["method"]).startswith("invent") or str(candidate["method"]) == "short"
        ]

        self.assertTrue(generated)
        self.assertTrue(all(_is_pronounceable(str(candidate["name"])) for candidate in generated))
        self.assertTrue(any(str(candidate["method"]) == "short" and len(str(candidate["name"])) == 4 for candidate in generated))


if __name__ == "__main__":
    unittest.main()
