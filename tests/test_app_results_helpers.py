"""Tests for Streamlit result-table helpers."""

from __future__ import annotations

from decimal import Decimal

from app import _backend_status_label, _backend_value_label, build_results_table


def test_backend_value_label_formats_valued_range() -> None:
    label = _backend_value_label(
        {
            "status": "valued",
            "estimated_value_min": Decimal("1250.49"),
            "estimated_value_max": Decimal("2750.51"),
            "currency": "USD",
        }
    )

    assert label == "USD 1,250 - USD 2,751", f"Unexpected backend value label: {label!r}"


def test_backend_status_label_includes_tier_and_confidence() -> None:
    label = _backend_status_label(
        {
            "status": "needs_review",
            "value_tier": "meaningful",
            "confidence_level": "medium",
        }
    )

    assert label == "Needs Review · Meaningful · Medium confidence"


def test_build_results_table_surfaces_backend_valuation_context() -> None:
    table = build_results_table(
        [
            {
                "domain": "atlasai.com",
                "niche": "Tech & SaaS",
                "tld": ".com",
                "final_score": 82,
                "backend_valuation": {
                    "status": "valued",
                    "estimated_value_min": Decimal("1000"),
                    "estimated_value_max": Decimal("2500"),
                    "currency": "USD",
                    "value_tier": "meaningful",
                    "confidence_level": "medium",
                },
                "grade": "A",
                "method": "brandable",
                "improvement_delta": 0,
                "profile": "startup_brand",
                "explanation": "Strong short brandable domain.",
            }
        ],
        {"atlasai.com": "Available"},
    )

    row = table.iloc[0].to_dict()
    assert row["Backend Valuation"] == "USD 1,000 - USD 2,500"
    assert row["Backend Status"] == "Valued · Meaningful · Medium confidence"
    assert row["Profile"] == "Startup Brand"
    assert row["Availability"] == "Available"
