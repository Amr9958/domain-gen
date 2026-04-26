"""Repositories for appraisal report generation and retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from domain_intel.contracts.appraisal import AppraisalReportContract
from domain_intel.db.models import AIExplanation, AppraisalReport, Auction, DerivedSignal, Domain, OrganizationMember, ValuationRun, VerifiedFact
from domain_intel.repositories.base import BaseRepository
from domain_intel.services.report_service import (
    AppraisalReportRecord,
    GenerateAppraisalReportCommand,
    ReportAIExplanationInput,
    ReportAuctionInput,
    ReportClassificationInput,
    ReportCompositionInput,
    ReportDomainInput,
    ReportFactInput,
    ReportReasonCodeInput,
    ReportSignalInput,
    ReportValuationInput,
)


class AppraisalReportRepository(BaseRepository):
    """SQLAlchemy-backed report repository."""

    def load_report_input(self, command: GenerateAppraisalReportCommand) -> Optional[ReportCompositionInput]:
        """Load the structured inputs required for deterministic report generation."""

        if command.created_by_user_id is None:
            return None
        if not self._user_belongs_to_org(command.organization_id, command.created_by_user_id):
            raise PermissionError("created_by_user_id is not a member of the requested organization.")

        valuation = self.session.scalar(
            select(ValuationRun)
            .options(
                joinedload(ValuationRun.classification_result),
                joinedload(ValuationRun.reason_codes),
            )
            .where(
                ValuationRun.id == command.valuation_run_id,
                ValuationRun.domain_id == command.domain_id,
            )
        )
        if valuation is None:
            return None

        domain = self.session.get(Domain, command.domain_id)
        if domain is None:
            return None

        auction = None
        if valuation.auction_id is not None:
            auction = self.session.scalar(
                select(Auction)
                .options(joinedload(Auction.marketplace))
                .where(Auction.id == valuation.auction_id)
            )

        fact_ids = list(valuation.input_fact_ids)
        signal_ids = list(valuation.input_signal_ids)
        classification = valuation.classification_result
        if classification is not None:
            fact_ids = list({*fact_ids, *classification.input_fact_ids})
            signal_ids = list({*signal_ids, *classification.input_signal_ids})

        facts = []
        if fact_ids:
            facts = list(
                self.session.scalars(
                    select(VerifiedFact).where(VerifiedFact.id.in_(fact_ids))
                ).all()
            )

        signals = []
        if signal_ids:
            signals = list(
                self.session.scalars(
                    select(DerivedSignal).where(DerivedSignal.id.in_(signal_ids))
                ).all()
            )

        explanations = []
        if command.include_ai_explanations:
            explanations = list(
                self.session.scalars(
                    select(AIExplanation).where(
                        AIExplanation.subject_type == "valuation_run",
                        AIExplanation.subject_id == command.valuation_run_id,
                        AIExplanation.validation_status == "validated",
                    )
                ).all()
            )

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
                        evidence_refs_json=list(reason.evidence_refs_json),
                        explanation=reason.explanation,
                    )
                    for reason in valuation.reason_codes
                ],
            ),
            classification=(
                ReportClassificationInput(
                    id=classification.id,
                    domain_type=classification.domain_type.value if classification.domain_type else None,
                    business_category=classification.business_category,
                    language_code=classification.language_code,
                    tokens_json=list(classification.tokens_json),
                    risk_flags_json=list(classification.risk_flags_json),
                    confidence_score=classification.confidence_score,
                    refusal_reason=classification.refusal_reason,
                    created_at=classification.created_at,
                )
                if classification is not None
                else None
            ),
            auction=(
                ReportAuctionInput(
                    id=auction.id,
                    marketplace_code=auction.marketplace.code if auction.marketplace else None,
                    auction_type=auction.auction_type.value,
                    status=auction.status.value,
                    source_url=auction.source_url,
                    ends_at=auction.ends_at,
                    current_bid_amount=auction.current_bid_amount,
                    currency=auction.currency,
                    bid_count=auction.bid_count,
                    watchers_count=auction.watchers_count,
                )
                if auction is not None
                else None
            ),
            facts=[
                ReportFactInput(
                    id=fact.id,
                    fact_type=fact.fact_type,
                    fact_key=fact.fact_key,
                    fact_value_json=_as_dict(fact.fact_value_json),
                    source_system=fact.source_system,
                    source_url=fact.source_url,
                    observed_at=fact.observed_at,
                )
                for fact in facts
            ],
            signals=[
                ReportSignalInput(
                    id=signal.id,
                    signal_type=signal.signal_type,
                    signal_key=signal.signal_key,
                    signal_value_json=_as_dict(signal.signal_value_json),
                    confidence_score=signal.confidence_score,
                    generated_at=signal.generated_at,
                )
                for signal in signals
            ],
            validated_ai_explanations=[
                ReportAIExplanationInput(
                    id=explanation.id,
                    explanation_type=explanation.explanation_type,
                    model_name=explanation.model_name,
                    prompt_version=explanation.prompt_version,
                    text=explanation.text,
                    validation_status=explanation.validation_status,
                )
                for explanation in explanations
            ],
            report_template_version=command.report_template_version,
        )

    def create_report(
        self,
        *,
        organization_id,
        domain_id,
        valuation_run_id,
        status: str,
        report_template_version: str,
        report_json: Dict[str, Any],
        generated_at,
        created_by_user_id,
    ) -> AppraisalReportRecord:
        """Persist a generated appraisal report and return a typed read model."""

        report = AppraisalReport(
            organization_id=organization_id,
            domain_id=domain_id,
            valuation_run_id=valuation_run_id,
            status=status,
            report_template_version=report_template_version,
            report_json=report_json,
            generated_at=generated_at,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return self._to_record(report)

    def get_report(self, report_id, organization_id) -> Optional[AppraisalReportRecord]:
        """Read a stored report by id within a required organization scope."""

        statement = select(AppraisalReport).where(
            AppraisalReport.id == report_id,
            AppraisalReport.organization_id == organization_id,
        )
        report = self.session.scalar(statement)
        if report is None:
            return None
        return self._to_record(report)

    def _user_belongs_to_org(self, organization_id, user_id) -> bool:
        return (
            self.session.scalar(
                select(OrganizationMember.user_id).where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                )
            )
            is not None
        )

    def _to_record(self, report: AppraisalReport) -> AppraisalReportRecord:
        return AppraisalReportRecord(
            id=report.id,
            organization_id=report.organization_id,
            domain_id=report.domain_id,
            valuation_run_id=report.valuation_run_id,
            status=report.status,
            report_template_version=report.report_template_version,
            generated_at=report.generated_at,
            expires_at=report.expires_at,
            created_by_user_id=report.created_by_user_id,
            report_json=_parse_report_contract(report.report_json),
        )


def _parse_report_contract(payload: Dict[str, Any]) -> AppraisalReportContract:
    if hasattr(AppraisalReportContract, "model_validate"):
        return AppraisalReportContract.model_validate(payload)
    return AppraisalReportContract.parse_obj(payload)


def _as_dict(payload: object) -> Dict[str, object]:
    return payload if isinstance(payload, dict) else {"value": payload}
