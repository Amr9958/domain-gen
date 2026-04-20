"""Tests for trend-derived domain opportunity generation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from processors.opportunities import _contextual_score_adjustment, generate_domain_opportunities
from scoring.interfaces import DomainAppraisal
from tests.helpers import make_keyword, make_theme


def _fake_appraisal(domain: str, profile: str = "startup_brand", niche: str = "", word_banks=None) -> DomainAppraisal:
    _ = niche, word_banks
    name, suffix = domain.rsplit(".", 1)
    return DomainAppraisal(
        domain=domain,
        name=name,
        tld=f".{suffix}",
        profile=profile,
        final_score=90,
        grade="A",
        tier="Premium",
        value="$2,500-$5,000",
        subscores={"linguistic": 25, "brandability": 20},
        warnings=(),
        explanation="Strong buyer fit.",
        rejected=False,
    )


class OpportunityGenerationTests(unittest.TestCase):
    def test_contextual_adjustment_rejects_exact_source_entity_overlap(self) -> None:
        theme = make_theme(
            "Swarm Agent",
            related_terms=("agent", "swarm"),
            source_entities=("SwarmAgent",),
        )
        keyword = make_keyword("swarmagent", theme_name="Swarm Agent")

        adjustment, notes, context_rejected = _contextual_score_adjustment(
            "swarmagent",
            "exact",
            keyword,
            theme,
            "startup_brand",
        )

        self.assertTrue(context_rejected)
        self.assertLessEqual(adjustment, -22)
        self.assertTrue(any("source-specific project or brand term" in note for note in notes))

    @patch("processors.opportunities.load_word_banks", return_value={"modifiers": [], "nouns": []})
    @patch("processors.opportunities.generate_domains", return_value=[])
    @patch("processors.opportunities.evaluate_domain", side_effect=_fake_appraisal)
    def test_generate_domain_opportunities_downgrades_source_overlap_candidates(
        self,
        mocked_evaluate_domain,
        mocked_generate_domains,
        mocked_load_word_banks,
    ) -> None:
        theme = make_theme(
            "Swarm Agent",
            related_terms=("agent", "swarm"),
            source_entities=("swarmagent",),
        )
        keyword = make_keyword(
            "swarmagent",
            theme_name="Swarm Agent",
            commercial_score=4.8,
            novelty_score=4.1,
            brandability_score=4.2,
        )

        opportunities = generate_domain_opportunities([keyword], [theme])

        exact_overlap = next(
            opportunity
            for opportunity in opportunities
            if opportunity.domain_name == "swarmagent" and opportunity.extension == ".com"
        )

        self.assertEqual(exact_overlap.review_bucket, "rejected")
        self.assertEqual(exact_overlap.recommendation.value, "skip")
        self.assertTrue(any("source-specific project or brand term" in note for note in exact_overlap.risk_notes))
        self.assertGreater(mocked_evaluate_domain.call_count, 0)
        mocked_generate_domains.assert_called()
        mocked_load_word_banks.assert_called_once()


if __name__ == "__main__":
    unittest.main()
