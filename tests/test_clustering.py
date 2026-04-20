"""Tests for lightweight signal clustering."""

from __future__ import annotations

import unittest

from processors.clustering import cluster_processed_items
from tests.helpers import make_content_item


class ClusteringTests(unittest.TestCase):
    def test_related_items_share_cluster_key_and_compound_metadata(self) -> None:
        items = [
            make_content_item(
                title="AI agents security guardrails",
                summary="agent security controls for runtime systems",
                tags=("agents", "security"),
                content_hash="item-1",
                source_name="github",
            ),
            make_content_item(
                title="Agent security platform for enterprise teams",
                summary="security workflows for agent deployment",
                tags=("agent", "security"),
                content_hash="item-2",
                source_name="hacker_news",
            ),
            make_content_item(
                title="Payment ledger automation for fintech operators",
                summary="ledger workflow for billing teams",
                tags=("payment", "ledger"),
                content_hash="item-3",
            ),
        ]

        clustered = cluster_processed_items(items)

        self.assertEqual(clustered[0].cluster_key, clustered[1].cluster_key)
        self.assertIn("agent-security", clustered[0].cluster_terms)
        self.assertEqual(clustered[0].cluster_size, 2)
        self.assertEqual(clustered[0].source_diversity, 2)
        self.assertGreaterEqual(clustered[0].shared_term_count, 1)
        self.assertNotEqual(clustered[0].cluster_key, clustered[2].cluster_key)


if __name__ == "__main__":
    unittest.main()
