"""Domain classification service tests."""

from __future__ import annotations

from uuid import uuid4

from domain_intel.core.enums import DomainType
from domain_intel.services.classification_service import (
    DomainClassificationInput,
    DomainClassificationService,
)


def test_classification_service_detects_brandable() -> None:
    draft = _classify("zorvia.com", "zorvia", style="brandable")

    assert draft.domain_type is DomainType.BRANDABLE
    assert draft.tokens == ("zorvia",)


def test_classification_service_detects_exact_match_from_profile() -> None:
    draft = _classify("cloudstorage.com", "cloudstorage", scoring_profile="exact_match")

    assert draft.domain_type is DomainType.EXACT_MATCH


def test_classification_service_detects_geo_from_context() -> None:
    draft = _classify("miamiplumber.com", "miamiplumber", niche="local plumbing")

    assert draft.domain_type is DomainType.GEO


def test_classification_service_detects_typo_risk_from_notes() -> None:
    draft = _classify("gooogletools.com", "gooogletools", risk_notes=("Potential typo confusion.",))

    assert draft.domain_type is DomainType.TYPO_RISK
    assert draft.risk_flags == ("typo_confusion",)


def test_classification_service_keeps_unknown_when_no_signal_or_hint_matches() -> None:
    draft = _classify("zzqjxq.com", "zzqjxq")

    assert draft.domain_type is DomainType.UNKNOWN
    assert draft.refusal_reason is not None
    assert draft.confidence_score <= 0.45


def test_classification_service_carries_input_fact_and_signal_ids() -> None:
    fact_id = uuid4()
    signal_id = uuid4()
    service = DomainClassificationService(algorithm_version="test-classifier")

    draft = service.build_classification(
        DomainClassificationInput(
            domain_id=uuid4(),
            fqdn="zorvia.com",
            sld="zorvia",
            tld="com",
            style="brandable",
            input_fact_ids=(fact_id,),
            input_signal_ids=(signal_id,),
        )
    )

    assert draft.input_fact_ids == (fact_id,)
    assert draft.input_signal_ids == (signal_id,)


def _classify(
    fqdn: str,
    sld: str,
    *,
    scoring_profile: str = "",
    style: str = "",
    niche: str = "",
    risk_notes: tuple[str, ...] = tuple(),
):
    service = DomainClassificationService(algorithm_version="test-classifier")
    return service.build_classification(
        DomainClassificationInput(
            domain_id=uuid4(),
            fqdn=fqdn,
            sld=sld,
            tld=fqdn.rsplit(".", 1)[-1],
            scoring_profile=scoring_profile,
            style=style,
            niche=niche,
            risk_notes=risk_notes,
        )
    )
