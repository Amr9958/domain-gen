"""Generated-domain valuation bridge service tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from domain_intel.core.enums import DomainType
from domain_intel.db.models import ClassificationResult, DerivedSignal, Domain, ValuationRun
from domain_intel.services.generated_domain_service import (
    GeneratedDomainValuationCommand,
    GeneratedDomainValuationService,
    build_generated_domain_valuation_request,
    normalize_generated_domain,
    punycode_domain,
)


def test_normalize_generated_domain_accepts_matching_full_domain_and_extension() -> None:
    assert normalize_generated_domain(" WWW.AtlasAI.com ", " .COM ") == ("atlasai.com", "atlasai", "com")
    assert normalize_generated_domain("atlasai.com", "") == ("atlasai.com", "atlasai", "com")
    assert normalize_generated_domain("atlasai.co.uk", ".co.uk") == ("atlasai.co.uk", "atlasai", "co.uk")


@pytest.mark.parametrize(
    ("domain_name", "extension"),
    [
        ("", "com"),
        ("atlasai", ""),
        ("atlasai.net", "com"),
        ("atlas.ai.tools", "tools"),
    ],
)
def test_normalize_generated_domain_rejects_invalid_identity(domain_name: str, extension: str) -> None:
    with pytest.raises(ValueError, match="valid SLD and extension"):
        normalize_generated_domain(domain_name, extension)


def test_punycode_domain_translates_unicode_fqdn() -> None:
    assert punycode_domain("caf\u00e9.com") == "xn--caf-dma.com"


def test_upsert_domain_reuses_existing_domain() -> None:
    existing = Domain(
        id=uuid4(),
        fqdn="atlasai.com",
        sld="old",
        tld="net",
        punycode_fqdn="old.net",
        unicode_fqdn="old.net",
        is_valid=False,
    )
    session = ExistingDomainSession(existing)
    service = GeneratedDomainValuationService(session=session)

    domain = service._upsert_domain(fqdn="atlasai.com", sld="atlasai", tld="com")

    assert domain is existing
    assert session.added == []
    assert session.flush_count == 1
    assert existing.sld == "atlasai"
    assert existing.tld == "com"
    assert existing.punycode_fqdn == "atlasai.com"
    assert existing.unicode_fqdn == "atlasai.com"
    assert existing.is_valid is True


def test_build_generated_domain_valuation_request_uses_classification_and_signals() -> None:
    domain_id = uuid4()
    classification_id = uuid4()
    signal_id = uuid4()
    generated_at = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    domain = Domain(
        id=domain_id,
        fqdn="atlasai.com",
        sld="atlasai",
        tld="com",
        punycode_fqdn="atlasai.com",
        unicode_fqdn="atlasai.com",
        is_valid=True,
    )
    classification = ClassificationResult(
        id=classification_id,
        domain_id=domain_id,
        domain_type=DomainType.BRANDABLE,
        business_category="Tech & SaaS",
        language_code="en",
        tokens_json=["atlas", "ai"],
        risk_flags_json=["trademark_risk", "typo_confusion", "adult_or_sensitive"],
        confidence_score=Decimal("0.8200"),
        algorithm_version="generated-domain-bridge-v1",
        input_fact_ids=[],
        input_signal_ids=[signal_id],
        refusal_reason=None,
        created_at=generated_at,
    )
    signal = DerivedSignal(
        id=signal_id,
        domain_id=domain_id,
        auction_id=None,
        signal_type="legacy_scoring",
        signal_key="legacy_scoring_score",
        signal_value_json={"score": 150},
        input_fact_ids=[],
        input_signal_ids=[],
        algorithm_version="generated-domain-bridge-v1",
        confidence_score=Decimal("1.0000"),
        generated_at=generated_at,
    )

    request = build_generated_domain_valuation_request(
        domain=domain,
        command=GeneratedDomainValuationCommand(
            domain_name="atlasai",
            extension="com",
            score=150,
            source_theme="ai agents",
            risk_notes=("Needs trademark review.",),
        ),
        classification=classification,
        signals=[signal],
    )

    assert request.domain.id == domain_id
    assert request.classification is not None
    assert request.classification.classification_result_id == classification_id
    assert request.classification.tokens == ("atlas", "ai")
    assert request.classification.risk_flags == ("trademark_risk", "typo_confusion", "adult_or_sensitive")
    assert request.market_signals.commercial_intent_score == 1.0
    assert request.market_signals.search_demand_score == 1.0
    assert request.market_signals.trend_score == 1.0
    assert request.market_signals.liquidity_score == 1.0
    assert request.risk_signals.trademark_risk_score == 0.72
    assert request.risk_signals.typo_confusion_score == 0.72
    assert request.risk_signals.adult_sensitivity_score == 0.55
    assert request.risk_signals.legal_notes == ("Needs trademark review.",)
    assert request.input_fact_ids == tuple()
    assert request.input_signal_ids == (signal_id,)
    assert request.market_signals.evidence_refs[0].id == str(signal_id)


def test_build_generated_domain_valuation_request_tolerates_missing_json_lists() -> None:
    domain_id = uuid4()
    classification = ClassificationResult(
        id=uuid4(),
        domain_id=domain_id,
        domain_type=DomainType.BRANDABLE,
        business_category=None,
        language_code="en",
        tokens_json=None,
        risk_flags_json=None,
        confidence_score=Decimal("0.6500"),
        algorithm_version="generated-domain-bridge-v1",
        input_fact_ids=[],
        input_signal_ids=[],
        refusal_reason=None,
        created_at=datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc),
    )

    request = build_generated_domain_valuation_request(
        domain=Domain(
            id=domain_id,
            fqdn="atlasai.com",
            sld="atlasai",
            tld="com",
            punycode_fqdn="atlasai.com",
            unicode_fqdn="atlasai.com",
            is_valid=True,
        ),
        command=GeneratedDomainValuationCommand(domain_name="atlasai", extension="com", score=82),
        classification=classification,
        signals=[],
    )

    assert request.classification is not None
    assert request.classification.tokens == tuple()
    assert request.classification.risk_flags == tuple()
    assert request.risk_signals.trademark_risk_score is None


def test_generated_domain_service_values_mcp_keyword_with_bridge_boundaries() -> None:
    session = CapturingGeneratedDomainSession()
    valuation_repository = CapturingValuationRepository()
    service = GeneratedDomainValuationService(session=session, valuation_repository=valuation_repository)

    record = service.value_generated_domain(
        GeneratedDomainValuationCommand(
            domain_name="mcpagent",
            extension="com",
            score=84,
            grade="A",
            scoring_profile="startup_brand",
            value_estimate="$1k-$3k",
            source_theme="mcp tooling",
            keyword="mcp",
            review_bucket="shortlist",
            recommendation="shortlist",
            style="compound",
            niche="Tech & SaaS",
            buyer_type="startup",
        )
    )

    domain = session.single_added(Domain)
    classification = session.single_added(ClassificationResult)
    signals = session.added_of_type(DerivedSignal)
    signal_ids = [signal.id for signal in signals]

    assert record.fqdn == "mcpagent.com"
    assert record.classification_result_id == classification.id
    assert domain.fqdn == "mcpagent.com"
    assert signals
    assert "legacy_scoring_score" in {signal.signal_key for signal in signals}
    assert "legacy_generation_keyword" in {signal.signal_key for signal in signals}
    assert all(signal.input_fact_ids == [] for signal in signals)
    assert classification.input_fact_ids == []
    assert classification.input_signal_ids == signal_ids
    assert valuation_repository.command is not None
    assert valuation_repository.command.classification_result_id == classification.id
    assert valuation_repository.command.input_fact_ids == tuple()
    assert valuation_repository.command.input_signal_ids == tuple(signal_ids)
    assert session.commit_count == 1


class ExistingDomainSession:
    def __init__(self, domain: Domain) -> None:
        self.domain = domain
        self.added = []
        self.flush_count = 0

    def scalar(self, _statement):
        return self.domain

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        self.flush_count += 1


class CapturingGeneratedDomainSession:
    def __init__(self) -> None:
        self.added = []
        self.commit_count = 0

    def scalar(self, _statement):
        return None

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()

    def commit(self) -> None:
        self.commit_count += 1

    def single_added(self, model_type):
        rows = self.added_of_type(model_type)
        assert len(rows) == 1
        return rows[0]

    def added_of_type(self, model_type):
        return [item for item in self.added if isinstance(item, model_type)]


class CapturingValuationRepository:
    def __init__(self) -> None:
        self.command = None

    def upsert_result(self, command):
        self.command = command
        result = command.result
        return ValuationRun(
            id=uuid4(),
            domain_id=command.domain_id,
            auction_id=command.auction_id,
            classification_result_id=command.classification_result_id,
            status=result.status,
            refusal_code=result.refusal_code,
            refusal_reason=result.refusal_reason,
            estimated_value_min=result.estimated_value_min,
            estimated_value_max=result.estimated_value_max,
            estimated_value_point=result.estimated_value_point,
            currency="USD",
            value_tier=result.value_tier,
            confidence_level=result.confidence.level,
            algorithm_version=command.algorithm_version or result.algorithm_version,
            input_fact_ids=list(command.input_fact_ids or result.input_fact_ids),
            input_signal_ids=list(command.input_signal_ids or result.input_signal_ids),
            created_at=datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
            reason_codes=[],
        )
