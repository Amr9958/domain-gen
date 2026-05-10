"""Tests for automatic scoring profile detection."""

from __future__ import annotations

import unittest

from scoring.score_profiles import auto_detect_profile


class AutoDetectProfileTests(unittest.TestCase):
    def test_geo_local_domains_are_detected(self) -> None:
        self.assertEqual(auto_detect_profile("dubaidental", ".com", ("dubai", "dental"), "Health & Medical"), "geo_local")
        self.assertEqual(auto_detect_profile("cairolegal", ".com", ("cairo", "legal"), "Legal & Professional"), "geo_local")

    def test_exact_authority_domains_are_detected(self) -> None:
        self.assertEqual(auto_detect_profile("repairtools", ".com", ("repair", "tools"), ""), "seo_authority")

    def test_brandable_and_non_com_domains_default_to_startup_brand(self) -> None:
        self.assertEqual(auto_detect_profile("nexaflow", ".ai", ("nexa", "flow"), "Tech & SaaS"), "startup_brand")
        self.assertEqual(auto_detect_profile("payflow", ".io", ("pay", "flow"), "Finance & Fintech"), "startup_brand")
        self.assertEqual(auto_detect_profile("cloudstackpromptlabs", ".io", ("cloud", "stack", "prompt", "labs"), "Tech & SaaS"), "startup_brand")

    def test_short_single_com_domains_are_flip_fast(self) -> None:
        self.assertEqual(auto_detect_profile("data", ".com", ("data",), "Tech & SaaS"), "flip_fast")


if __name__ == "__main__":
    unittest.main()
