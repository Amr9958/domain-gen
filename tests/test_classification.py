"""Tests for topic-quality classification heuristics."""

from __future__ import annotations

import unittest

from models import ItemClassification, SourceType
from processors.classification import classify_content_item
from tests.helpers import make_content_item


class ClassificationTests(unittest.TestCase):
    def test_multi_source_repeated_topic_gets_investable_boost(self) -> None:
        item = make_content_item(
            title="Agent security runtime guardrails for production teams",
            summary="policy controls for AI agent deployment and observability",
            tags=("agent", "security", "observability"),
            source_type=SourceType.REPOSITORY,
            source_name="github",
            content_hash="agent-security-item",
        )

        result = classify_content_item(
            item,
            ("agent-security", "observability"),
            cluster_size=3,
            shared_term_count=2,
            source_diversity=2,
        )

        self.assertEqual(result.classification, ItemClassification.INVESTABLE)
        self.assertGreaterEqual(result.score, 4.5)
        self.assertTrue(any("multiple sources" in reason for reason in result.reasons))

    def test_patch_unlocker_support_noise_gets_downgraded(self) -> None:
        item = make_content_item(
            title="PassFab iPhone Unlocker Latest Patch",
            summary="Windows guide to bypass lockscreen installation support",
            tags=("unlocker", "windows-guide", "patch"),
            source_type=SourceType.REPOSITORY,
            source_name="github",
            content_hash="unlocker-item",
        )

        result = classify_content_item(
            item,
            ("unlocker-patch",),
            cluster_size=1,
            shared_term_count=0,
            source_diversity=1,
        )

        self.assertEqual(result.classification, ItemClassification.IGNORE)
        self.assertLess(result.score, 1.0)
        self.assertTrue(any("support / patch phrasing" in reason for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
