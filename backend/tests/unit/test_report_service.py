"""Unit tests for appraisal report composition."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from domain_intel.contracts.appraisal import AppraisalReportContract
from domain_intel.services.report_service import (
    AppraisalReportRecord,
    GenerateAppraisalReportCommand,
    ReportAIExplanationInput,
    ReportClassificationInput,
    ReportCompositionInput,
    ReportDomainInput,
    ReportFactInput,
    ReportReasonCodeInput,
    ReportService,
    ReportSignalInput,
    ReportValuationInput,
    compose_appraisal_report,
)


def test_compose_appraisal_report_keeps_pricing_states_separate() -> None:
    report = compose_appraisal_report(_build_report_input())

    assert report.domain_header.fqdn == "atlasai.com"
    assert report.recommended_listing_price.amount == "2750.00"
    assert report.recommended_listing_price.currency == "USD"
    assert report.fair_market_range.low == "2000.00"
    assert report.fair_market_range.high == "3500.00"
    assert report.pricing_guidance.estimated_wholesale_range.low == "750.00"
    assert report.pricing_guidance.estimated_wholesale_range.high == "1250.00"
    assert report.pricing_guidance.minimum_acceptable_offer.amount == "2000.00"
    assert report.whois_intelligence.registrar == "Example Registrar"
    assert report.tld_ecosystem_summary.registered_extensions == ["atlasai.net", "atlasai.io"]
    assert report.market_analysis_summary.bid_to_estimated_wholesale_ratio is None
    assert report.score_breakdown.overall_investment_score == 0.72
    assert report.final_verdict.status == "valued"


def test_report_service_generates_and_persists_typed_report() -> None:
    fake_repository = FakeReportRepository(_build_report_input())
    service = ReportService(fake_repository)
    command = GenerateAppraisalReportCommand(
        organization_id=uuid4(),
        domain_id=fake_repository.report_input.domain.id,
        valuation_run_id=fake_repository.report_input.valuation.id,
        include_ai_explanations=True,
        report_template_version="appraisal-v1",
        created_by_user_id=uuid4(),
    )

    record = service.generate_appraisal_report(command)

    assert fake_repository.created_kwargs["status"] == "generated"
    assert record.report_json.final_verdict.pricing_posture == "bin"
    assert record.report_json.validated_ai_explanations[0].explanation_type == "appraisal_summary"


def test_report_service_requires_organization_scope_for_reads() -> None:
    fake_repository = FakeReportRepository(_build_report_input())
    service = ReportService(fake_repository)

    try:
        service.get_appraisal_report(report_id=uuid4(), organization_id=None)
    except ValueError as exc:
        assert "organization_id is required" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError for unscoped report retrieval.")


class FakeReportRepository:
    def __init__(self, report_input: ReportCompositionInput) -> None:
        self.report_input = report_input
        self.created_kwargs = {}

    def load_report_input(self, command: GenerateAppraisalReportCommand) -> ReportCompositionInput:
        assert command.domain_id == self.report_input.domain.id
        return self.report_input

    def create_report(self, **kwargs) -> AppraisalReportRecord:
        self.created_kwargs = kwargs
        payload = kwargs["report_json"]
        report_json = (
            AppraisalReportContract.model_validate(payload)
            if hasattr(AppraisalReportContract, "model_validate")
            else AppraisalReportContract.parse_obj(payload)
        )
        return AppraisalReportRecord(
            id=uuid4(),
            organization_id=kwargs["organization_id"],
            domain_id=kwargs["domain_id"],
            valuation_run_id=kwargs["valuation_run_id"],
            status=kwargs["status"],
            report_template_version=kwargs["report_template_version"],
            generated_at=kwargs["generated_at"],
            expires_at=None,
            created_by_user_id=kwargs["created_by_user_id"],
            report_json=report_json,
        )

    def get_report(self, report_id, organization_id):
        raise AssertionError("get_report should not be called in this test")


def _build_report_input() -> ReportCompositionInput:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    domain_id = uuid4()
    valuation_id = uuid4()
    classification_id = uuid4()
    return ReportCompositionInput(
        organization_id=uuid4(),
        domain=ReportDomainInput(
            id=domain_id,
            fqdn="atlasai.com",
            sld="atlasai",
            tld="com",
            punycode_fqdn="atlasai.com",
            unicode_fqdn="atlasai.com",
            is_valid=True,
        ),
        valuation=ReportValuationInput(
            id=valuation_id,
            status="valued",
            refusal_code=None,
            refusal_reason=None,
            estimated_value_min=Decimal("2000"),
            estimated_value_max=Decimal("3500"),
            estimated_value_point=Decimal("2750"),
            currency="USD",
            value_tier="meaningful",
            confidence_level="high",
            algorithm_version="valuation-v1",
            input_fact_ids=[],
            input_signal_ids=[],
            created_at=now,
            reason_codes=[
                ReportReasonCodeInput(
                    id=uuid4(),
                    code="clean_com",
                    label=".com liquidity",
                    direction="positive",
                    impact_amount=Decimal("500"),
                    impact_weight=Decimal("0.30"),
                    evidence_refs_json=[],
                    explanation=".com supports broad buyer familiarity.",
                ),
                ReportReasonCodeInput(
                    id=uuid4(),
                    code="limited_end_user_evidence",
                    label="Limited end-user evidence",
                    direction="negative",
                    impact_amount=Decimal("-250"),
                    impact_weight=Decimal("0.10"),
                    evidence_refs_json=[],
                    explanation="Retail ceiling remains moderate without stronger end-user proof.",
                ),
            ],
        ),
        classification=ReportClassificationInput(
            id=classification_id,
            domain_type="brandable",
            business_category="ai",
            language_code="en",
            tokens_json=["atlas", "ai"],
            risk_flags_json=[{"code": "brand_confusion_risk", "level": "warning", "summary": "Potential brand confusion."}],
            confidence_score=Decimal("0.91"),
            refusal_reason=None,
            created_at=now,
        ),
        auction=None,
        facts=[
            ReportFactInput(
                id=uuid4(),
                fact_type="whois",
                fact_key="registrar",
                fact_value_json={"value": "Example Registrar"},
                source_system="whois_provider",
                source_url=None,
                observed_at=now,
            ),
            ReportFactInput(
                id=uuid4(),
                fact_type="whois",
                fact_key="created_at",
                fact_value_json={"value": "2016-01-01T00:00:00+00:00"},
                source_system="whois_provider",
                source_url=None,
                observed_at=now,
            ),
            ReportFactInput(
                id=uuid4(),
                fact_type="whois",
                fact_key="expires_at",
                fact_value_json={"value": "2027-01-01T00:00:00+00:00"},
                source_system="whois_provider",
                source_url=None,
                observed_at=now,
            ),
            ReportFactInput(
                id=uuid4(),
                fact_type="whois",
                fact_key="nameservers",
                fact_value_json={"values": ["ns1.example.test", "ns2.example.test"]},
                source_system="whois_provider",
                source_url=None,
                observed_at=now,
            ),
            ReportFactInput(
                id=uuid4(),
                fact_type="tld_ecosystem",
                fact_key="registered_extensions",
                fact_value_json={"values": ["atlasai.net", "atlasai.io"]},
                source_system="registry_snapshot",
                source_url=None,
                observed_at=now,
            ),
        ],
        signals=[
            ReportSignalInput(
                id=uuid4(),
                signal_type="valuation_support",
                signal_key="estimated_wholesale_min",
                signal_value_json={"amount": "750"},
                confidence_score=Decimal("0.80"),
                generated_at=now,
            ),
            ReportSignalInput(
                id=uuid4(),
                signal_type="valuation_support",
                signal_key="estimated_wholesale_max",
                signal_value_json={"amount": "1250"},
                confidence_score=Decimal("0.80"),
                generated_at=now,
            ),
            ReportSignalInput(
                id=uuid4(),
                signal_type="score",
                signal_key="investment_score",
                signal_value_json={"score": "0.72", "summary": "Healthy liquidity and clean structure."},
                confidence_score=Decimal("0.88"),
                generated_at=now,
            ),
            ReportSignalInput(
                id=uuid4(),
                signal_type="score",
                signal_key="liquidity_score",
                signal_value_json={"score": "0.55"},
                confidence_score=Decimal("0.70"),
                generated_at=now,
            ),
            ReportSignalInput(
                id=uuid4(),
                signal_type="score",
                signal_key="risk_score",
                signal_value_json={"score": "0.20"},
                confidence_score=Decimal("0.90"),
                generated_at=now,
            ),
        ],
        validated_ai_explanations=[
            ReportAIExplanationInput(
                id=uuid4(),
                explanation_type="appraisal_summary",
                model_name="approved-model",
                prompt_version="appraisal-summary-v1",
                text="AtlasAI.com has solid brandable structure and moderate end-user upside.",
                validation_status="validated",
            )
        ],
        report_template_version="appraisal-v1",
    )
