"""Local performance smoke checks for root critical paths."""

from __future__ import annotations

import time
from collections import Counter

import pytest

from generator import _style_bucket, generate_domains


SMOKE_WORD_BANKS = {
    "abstract": ["nexus", "prime", "vertex", "zenith"],
    "power": ["apex", "bold", "elite", "surge"],
    "tech": ["agent", "api", "data", "deploy", "mesh", "stack", "sync"],
    "finance": ["audit", "fund", "ledger", "pay", "risk", "trade"],
    "common_modifiers": ["core", "edge", "flow", "hub", "labs", "pulse", "shift"],
    "brandable_fragments": ["canvas", "craft", "nexa", "pixel", "spark"],
    "premium_words": ["apex", "core", "mint", "nexus", "vault"],
    "short_prefixes": ["arc", "neo", "nex", "ori", "vox", "zen"],
}


@pytest.mark.performance
def test_offline_auto_generation_performance_smoke() -> None:
    start = time.perf_counter()
    candidates = generate_domains(
        niche="Tech & SaaS",
        use_llm=False,
        word_banks=SMOKE_WORD_BANKS,
        keywords_str="agentic, workflow, data, automation",
        num_per_tier=20,
    )
    elapsed = time.perf_counter() - start
    styles = Counter(_style_bucket(str(candidate["method"])) for candidate in candidates)

    assert elapsed < 2.0, (
        f"offline auto generation took {elapsed:.3f}s for {len(candidates)} candidates; "
        "expected the local generator path to stay below 2s"
    )
    assert len(candidates) >= 30, (
        f"expected at least 30 candidates from auto generation, got {len(candidates)}; "
        f"style distribution={dict(styles)}"
    )
    assert len(styles) >= 4, f"expected at least 4 style buckets, got {dict(styles)}"
