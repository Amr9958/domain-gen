"""Starter domain classification rule tests."""

from __future__ import annotations

from uuid import uuid4

from domain_intel.core.enums import DomainType, StarterDomainLabel
from domain_intel.enrichment.classification import StarterDomainClassificationEngine
from domain_intel.enrichment.contracts import DomainTarget


def _target(fqdn: str, sld: str, tld: str = "com") -> DomainTarget:
    return DomainTarget(
        domain_id=uuid4(),
        fqdn=fqdn,
        sld=sld,
        tld=tld,
        punycode_fqdn=fqdn,
        unicode_fqdn=fqdn,
    )


def test_geo_service_domains_get_geo_service_and_local_lead_gen_labels() -> None:
    engine = StarterDomainClassificationEngine()

    hint = engine.classify(_target("miamiplumber.com", "miamiplumber"))

    assert hint.primary_label == StarterDomainLabel.GEO_SERVICE
    assert hint.mapped_domain_type == DomainType.GEO
    assert {label.label for label in hint.labels} >= {
        StarterDomainLabel.GEO_SERVICE,
        StarterDomainLabel.LOCAL_LEAD_GEN,
    }


def test_ai_domains_get_ai_tech_label_with_technology_business_category() -> None:
    engine = StarterDomainClassificationEngine()

    hint = engine.classify(_target("vectorai.com", "vectorai"))

    assert hint.primary_label == StarterDomainLabel.AI_TECH
    assert hint.business_category == "technology"
    assert hint.tokens == ["vector", "ai"]


def test_pronounceable_made_up_domains_get_brandable_hints() -> None:
    engine = StarterDomainClassificationEngine()

    hint = engine.classify(_target("zorvia.com", "zorvia"))

    assert hint.primary_label == StarterDomainLabel.MADE_UP_BRAND
    assert {label.label for label in hint.labels} >= {
        StarterDomainLabel.MADE_UP_BRAND,
        StarterDomainLabel.BRANDABLE,
    }
    assert hint.mapped_domain_type == DomainType.BRANDABLE


def test_single_clean_dictionary_com_gets_dictionary_premium_hint() -> None:
    engine = StarterDomainClassificationEngine()

    hint = engine.classify(_target("atlas.com", "atlas"))

    assert hint.primary_label == StarterDomainLabel.DICTIONARY_PREMIUM
    assert hint.mapped_domain_type == DomainType.PREMIUM_GENERIC
    assert StarterDomainLabel.SHORT_DOMAIN in {label.label for label in hint.labels}
