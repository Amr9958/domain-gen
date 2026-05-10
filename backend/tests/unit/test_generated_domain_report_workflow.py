"""Integration-style test for generated-domain valuation and report composition."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from domain_intel.contracts.appraisal import AppraisalReportContract
from domain_intel.db.models import ClassificationResult, DerivedSignal, Domain, ValuationReasonCode, ValuationRun
from domain_intel.services.generated_domain_service import (
    GeneratedDomainValuationCommand,
    GeneratedDomainValuationService,
)
from domain_intel.services.report_service import (
    AppraisalReportRecord,
    GenerateAppraisalReportCommand,
    ReportClassificationInput,
    ReportCompositionInput,
    ReportDomainInput,
    ReportReasonCodeInput,
    ReportService,
    ReportSignalInput,
    ReportValuationInput,
)


def test_generated_domain_classification_valuation_report_workflow() -> None:
    session = WorkflowSession()
    valuation_repository = WorkflowValuationRepository()
    generated_service = GeneratedDomainValuationService(session=session, valuation_repository=valuation_repository)

    valuation_record = generated_service.value_generated_domain(
        GeneratedDomainValuationCommand(
            domain_name="atlasai",
            extension="com",
            score=82,
            grade="A",
            scoring_profile="startup_brand",
            value_estimate="$1k-$3k",
            source_theme="ai agents",
            keyword="agent",
            review_bucket="shortlist",
            recommendation="shortlist",
            style="brandable",
            niche="Tech & SaaS",
            buyer_type="startup",
        )
    )

    domain = session.single_added(Domain)
    classification = session.single_added(ClassificationResult)
    signals = session.added_of_type(DerivedSignal)
    report_service = ReportService(WorkflowReportRepository(session, valuation_repository))
    report_record = report_service.generate_appraisal_report(
        GenerateAppraisalReportCommand(
            organization_id=uuid4(),
            domain_id=domain.id,
            valuation_run_id=valuation_record.valuation_run_id,
            include_ai_explanations=False,
            report_template_version="appraisal-v1",
            created_by_user_id=uuid4(),
        )
    )

    assert session.commit_count == 1
    assert valuation_record.status == "needs_review"
    assert valuation_record.classification_result_id == classification.id
    assert classification.input_signal_ids == [signal.id for signal in signals]
    assert valuation_repository.run.input_signal_ids == [signal.id for signal in signals]
    assert report_record.status == "needs_review"
    assert report_record.report_json.domain_header.fqdn == "atlasai.com"
    assert report_record.report_json.valuation_status == "needs_review"
    assert report_record.report_json.classification.domain_type == "brandable"
    assert report_record.report_json.final_verdict.status == "needs_review"


class WorkflowSession:
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


class WorkflowValuationRepository:
    def __init__(self) -> None:
        self.run = None
        self.reason_codes = []

    def upsert_result(self, command):
        result = command.result
        self.run = ValuationRun(
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
            created_at=datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc),
        )
        self.reason_codes = [
            ValuationReasonCode(
                id=uuid4(),
                valuation_run_id=self.run.id,
                code=reason.code,
                label=reason.label,
                direction=reason.direction.value,
                impact_amount=reason.impact_amount,
                impact_weight=Decimal(str(reason.impact_weight)),
                evidence_refs_json=[],
                explanation=reason.explanation,
            )
            for reason in result.reason_codes
        ]
        self.run.reason_codes = self.reason_codes
        return self.run


class WorkflowReportRepository:
    def __init__(self, session: WorkflowSession, valuation_repository: WorkflowValuationRepository) -> None:
        self.session = session
        self.valuation_repository = valuation_repository

    def load_report_input(self, command: GenerateAppraisalReportCommand) -> ReportCompositionInput:
        domain = self.session.single_added(Domain)
        classification = self.session.single_added(ClassificationResult)
        valuation = self.valuation_repository.run
        assert valuation.id == command.valuation_run_id
        return ReportCompositionInput(
            organization_id=command.organization_id,
            domain=ReportDomainInput(
                id=domain.id,
                fqdn=domain.fqdn,
                sld=domain.sld,
                tld=domain.tld,
                punycode_fqdn=domain.punycode_fqdn,
                unicode_fqdn=domain.unicode_fqdn,
                is_valid=domain.is_valid,
            ),
            valuation=ReportValuationInput(
                id=valuation.id,
                status=valuation.status.value,
                refusal_code=valuation.refusal_code.value if valuation.refusal_code else None,
                refusal_reason=valuation.refusal_reason,
                estimated_value_min=valuation.estimated_value_min,
                estimated_value_max=valuation.estimated_value_max,
                estimated_value_point=valuation.estimated_value_point,
                currency=valuation.currency,
                value_tier=valuation.value_tier.value,
                confidence_level=valuation.confidence_level.value,
                algorithm_version=valuation.algorithm_version,
                input_fact_ids=list(valuation.input_fact_ids),
                input_signal_ids=list(valuation.input_signal_ids),
                created_at=valuation.created_at,
                reason_codes=[
                    ReportReasonCodeInput(
                        id=reason.id,
                        code=reason.code,
                        label=reason.label,
                        direction=reason.direction,
                        impact_amount=reason.impact_amount,
                        impact_weight=reason.impact_weight,
                        evidence_refs_json=reason.evidence_refs_json,
                        explanation=reason.explanation,
                    )
                    for reason in self.valuation_repository.reason_codes
                ],
            ),
            classification=ReportClassificationInput(
                id=classification.id,
                domain_type=classification.domain_type.value,
                business_category=classification.business_category,
                language_code=classification.language_code,
                tokens_json=list(classification.tokens_json),
                risk_flags_json=list(classification.risk_flags_json),
                confidence_score=classification.confidence_score,
                refusal_reason=classification.refusal_reason,
                created_at=classification.created_at,
            ),
            auction=None,
            facts=[],
            signals=[
                ReportSignalInput(
                    id=signal.id,
                    signal_type=signal.signal_type,
                    signal_key=signal.signal_key,
                    signal_value_json=signal.signal_value_json,
                    confidence_score=signal.confidence_score,
                    generated_at=signal.generated_at,
                )
                for signal in self.session.added_of_type(DerivedSignal)
            ],
            validated_ai_explanations=[],
            report_template_version=command.report_template_version,
        )

    def create_report(self, **kwargs) -> AppraisalReportRecord:
        payload = kwargs["report_json"]
        report_json = AppraisalReportContract.model_validate(payload)
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
        raise AssertionError("get_report should not be called in this workflow test")
