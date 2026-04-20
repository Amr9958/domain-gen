"""Tests for shared trend-dashboard dataframe helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from models import DomainRecommendation
from tests.helpers import make_opportunity, make_theme
from utils.trend_dashboard import (
    _filter_domain_ideas_dataframe,
    prepare_domain_ideas_dataframe,
    prepare_refined_keywords_dataframe,
    prepare_refined_themes_dataframe,
    prepare_themes_dataframe,
)


class TrendDashboardTests(unittest.TestCase):
    def test_prepare_domain_ideas_dataframe_sorts_by_bucket_then_recommendation_then_score(self) -> None:
        ideas = [
            make_opportunity("watchbox", recommendation=DomainRecommendation.WATCH, review_bucket="watchlist", score=70),
            make_opportunity("rejectbox", recommendation=DomainRecommendation.SKIP, review_bucket="rejected", score=88),
            make_opportunity("buybox", recommendation=DomainRecommendation.BUY, review_bucket="shortlist", score=81),
        ]

        domain_df = prepare_domain_ideas_dataframe(ideas)

        self.assertEqual(domain_df.iloc[0]["Domain"], "buybox.com")
        self.assertEqual(domain_df.iloc[0]["Bucket"], "Shortlist")
        self.assertEqual(domain_df.iloc[1]["Bucket"], "Watchlist")

    def test_filter_domain_ideas_dataframe_returns_early_without_bucket_column(self) -> None:
        domain_df = pd.DataFrame([{"Domain": "buybox.com", "Score": 88}])

        with patch("utils.trend_dashboard.st.selectbox") as mocked_selectbox:
            filtered_df = _filter_domain_ideas_dataframe(domain_df, "Shortlist")

        mocked_selectbox.assert_not_called()
        self.assertEqual(filtered_df.to_dict("records"), domain_df.to_dict("records"))

    def test_prepare_refined_theme_and_keyword_dataframes_rank_promoted_rows_first(self) -> None:
        refined_themes_df = prepare_refined_themes_dataframe(
            [
                {"theme": "Agent Search", "confidence": 6.9, "action": "watch"},
                {"theme": "Agent Security", "confidence": 8.7, "action": "promote"},
            ]
        )
        refined_keywords_df = prepare_refined_keywords_dataframe(
            [
                {"keyword": "agentsearch", "theme": "Agent Search", "action": "keep", "confidence": 6.5, "commercial_fit": 6.8, "naming_fit": 6.2},
                {"keyword": "agentguard", "theme": "Agent Security", "action": "promote", "confidence": 8.4, "commercial_fit": 8.6, "naming_fit": 8.2},
            ]
        )

        self.assertEqual(refined_themes_df.iloc[0]["Theme"], "Agent Security")
        self.assertEqual(refined_keywords_df.iloc[0]["Keyword"], "agentguard")

    def test_prepare_themes_dataframe_includes_structured_source_columns(self) -> None:
        themes_df = prepare_themes_dataframe(
            [
                make_theme(
                    "Agent Security",
                    source_names=("github", "hacker_news"),
                    source_types=("repository", "developer"),
                    source_breakdown=("github x2", "hacker_news x1"),
                    source_tags=("open_source", "security"),
                    source_entities=("agentguard", "swarmagent"),
                    cluster_keys=("repository-agent-security", "developer-security-runtime"),
                    evidence_titles=("Agent security runtime guardrails",),
                    reason_highlights=("confirmed by multiple sources",),
                    related_terms=("agent", "security", "runtime"),
                )
            ]
        )

        self.assertEqual(themes_df.iloc[0]["Theme"], "Agent Security")
        self.assertIn("github", themes_df.iloc[0]["Sources"])
        self.assertIn("agentguard", themes_df.iloc[0]["Source Entities"])
        self.assertIn("github x2", themes_df.iloc[0]["Source Breakdown"])
        self.assertIn("confirmed by multiple sources", themes_df.iloc[0]["Reason Highlights"])


if __name__ == "__main__":
    unittest.main()
