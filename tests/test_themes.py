"""Tests for theme consolidation and evidence building."""

from __future__ import annotations

import unittest

from models import ItemClassification, SourceType
from processors.themes import build_themes
from tests.helpers import make_processed_signal, make_theme


class ThemeTests(unittest.TestCase):
    def test_build_themes_merges_related_compound_clusters_and_collects_evidence(self) -> None:
        signals = [
            make_processed_signal(
                title="Agent security runtime guardrails",
                cluster_key="repository-agent-security",
                cluster_terms=("agent-security", "runtime", "guardrail"),
                reasons=("confirmed by multiple sources", "commercial terms: security, agent"),
                source_name="github",
                tags=("agent", "security"),
                content_hash="theme-signal-1",
            ),
            make_processed_signal(
                title="Security runtime policies for AI agents",
                cluster_key="developer-security-runtime",
                cluster_terms=("security-runtime", "agent", "policy"),
                reasons=("topic repeated across several signals", "commercial terms: security, workflow"),
                source_name="hacker_news",
                source_type=SourceType.DEVELOPER,
                tags=("runtime", "policy"),
                content_hash="theme-signal-2",
            ),
        ]

        themed_signals, themes = build_themes(signals)

        self.assertEqual(len(themes), 1)
        self.assertEqual(len(themed_signals), 2)
        theme = themes[0]
        self.assertTrue(theme.canonical_name)
        self.assertIn("github x1", theme.source_breakdown)
        self.assertIn("hacker_news x1", theme.source_breakdown)
        self.assertTrue(any("commercial terms" in reason for reason in theme.reason_highlights))
        self.assertTrue(any("Agent security runtime guardrails" == title for title in theme.evidence_titles))
        self.assertGreaterEqual(len(theme.cluster_keys), 2)

    def test_build_themes_keeps_existing_theme_name_when_new_cluster_matches_by_atoms(self) -> None:
        existing_theme = make_theme(
            "Agent Security",
            related_terms=("agent-security", "runtime", "guardrail"),
            source_names=("github",),
            source_types=("repository",),
            source_breakdown=("github x2",),
            cluster_keys=("repository-agent-security",),
            evidence_titles=("Existing title",),
            reason_highlights=("confirmed by multiple sources",),
        )
        signals = [
            make_processed_signal(
                title="Runtime policy enforcement for agents",
                cluster_key="developer-security-runtime",
                cluster_terms=("security-runtime", "policy", "agent"),
                classification=ItemClassification.WATCHLIST,
                signal_score=4.2,
                reasons=("topic repeated across more than one signal",),
                source_name="hacker_news",
                source_type=SourceType.DEVELOPER,
                content_hash="theme-existing-1",
            )
        ]

        _, themes = build_themes(signals, existing_themes=[existing_theme])

        self.assertEqual(len(themes), 1)
        self.assertEqual(themes[0].canonical_name, "Agent Security")
        self.assertIn("Consolidated with a previous run", themes[0].description)
        self.assertIn("Existing title", themes[0].evidence_titles)


if __name__ == "__main__":
    unittest.main()
