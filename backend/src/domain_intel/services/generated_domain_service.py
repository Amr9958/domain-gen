"""Backend trigger for valuing generated domain opportunities."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain_intel.db.models import ClassificationResult, DerivedSignal, Domain
from domain_intel.repositories.valuation_repository import PersistValuationRunCommand, ValuationRunRepository
from domain_intel.services.classification_service import DomainClassificationInput, DomainClassificationService
from domain_intel.services.derived_signal_service import DerivedSignalService, LegacyOpportunitySignalInput
from domain_intel.services.valuation_service import ValuationService
from domain_intel.valuation.models import (
    ClassificationSnapshot,
    DomainRecord,
    DomainValuationRequest,
    EvidenceRef,
    MarketDemandSignals,
    RiskSignals,
    TldEcosystemSignals,
)


GENERATED_DOMAIN_ALGORITHM_VERSION = "generated-domain-bridge-v1"


@dataclass(frozen=True)
class GeneratedDomainValuationCommand:
    """Generated-domain opportunity fields accepted by backend valuation."""

    domain_name: str
    extension: str
    score: float = 0.0
    grade: str = ""
    scoring_profile: str = ""
    value_estimate: str = ""
    source_theme: str = ""
    keyword: str = ""
    review_bucket: str = ""
    recommendation: str = ""
    style: str = ""
    niche: str = ""
    buyer_type: str = ""
    risk_notes: tuple[str, ...] = field(default_factory=tuple)
    rejected_reason: str = ""


@dataclass(frozen=True)
class GeneratedDomainValuationRecord:
    """Persisted valuation summary returned to API callers."""

    domain_id: UUID
    fqdn: str
    classification_result_id: UUID
    valuation_run_id: UUID
    status: str
    refusal_code: Optional[str]
    refusal_reason: Optional[str]
    estimated_value_min: Optional[Decimal]
    estimated_value_max: Optional[Decimal]
    estimated_value_point: Optional[Decimal]
    currency: str
    value_tier: str
    confidence_level: str
    reason_codes: list[str]


class GeneratedDomainValuationService:
    """Persist generated-domain inputs and run backend valuation."""

    def __init__(
        self,
        session: Session,
        valuation_service: ValuationService | None = None,
        signal_service: DerivedSignalService | None = None,
        classification_service: DomainClassificationService | None = None,
        valuation_repository: ValuationRunRepository | None = None,
    ) -> None:
        self.session = session
        self.valuation_service = valuation_service or ValuationService()
        self.signal_service = signal_service or DerivedSignalService(
            algorithm_version=GENERATED_DOMAIN_ALGORITHM_VERSION
        )
        self.classification_service = classification_service or DomainClassificationService(
            algorithm_version=GENERATED_DOMAIN_ALGORITHM_VERSION
        )
        self.valuation_repository = valuation_repository or ValuationRunRepository(session)

    def value_generated_domain(self, command: GeneratedDomainValuationCommand) -> GeneratedDomainValuationRecord:
        """Run generated-domain bridge logic for one domain and persist the result."""

        fqdn, sld, tld = normalize_generated_domain(command.domain_name, command.extension)
        domain = self._upsert_domain(fqdn=fqdn, sld=sld, tld=tld)
        signals = self.signal_service.upsert_domain_signals(
            session=self.session,
            domain_id=domain.id,
            drafts=self.signal_service.build_legacy_opportunity_drafts(to_legacy_signal_input(command)),
        )
        signal_ids = tuple(signal.id for signal in signals)
        classification_draft = self.classification_service.build_classification(
            to_classification_input(domain=domain, command=command, input_signal_ids=signal_ids)
        )
        classification = self.classification_service.upsert_classification(
            session=self.session,
            domain_id=domain.id,
            draft=classification_draft,
        )
        valuation_request = build_generated_domain_valuation_request(
            domain=domain,
            command=command,
            classification=classification,
            signals=signals,
        )
        result = self.valuation_service.value_domain(valuation_request)
        valuation_run = self.valuation_repository.upsert_result(
            PersistValuationRunCommand(
                domain_id=domain.id,
                classification_result_id=classification.id,
                result=result,
                input_signal_ids=signal_ids,
                algorithm_version=GENERATED_DOMAIN_ALGORITHM_VERSION,
            )
        )
        self.session.commit()
        return GeneratedDomainValuationRecord(
            domain_id=domain.id,
            fqdn=domain.fqdn,
            classification_result_id=classification.id,
            valuation_run_id=valuation_run.id,
            status=valuation_run.status.value,
            refusal_code=valuation_run.refusal_code.value if valuation_run.refusal_code else None,
            refusal_reason=valuation_run.refusal_reason,
            estimated_value_min=valuation_run.estimated_value_min,
            estimated_value_max=valuation_run.estimated_value_max,
            estimated_value_point=valuation_run.estimated_value_point,
            currency=valuation_run.currency,
            value_tier=valuation_run.value_tier.value,
            confidence_level=valuation_run.confidence_level.value,
            reason_codes=[reason.code for reason in valuation_run.reason_codes],
        )

    def _upsert_domain(self, *, fqdn: str, sld: str, tld: str) -> Domain:
        domain = self.session.scalar(select(Domain).where(Domain.fqdn == fqdn))
        punycode_fqdn = punycode_domain(fqdn)
        if domain is None:
            domain = Domain(
                fqdn=fqdn,
                sld=sld,
                tld=tld,
                punycode_fqdn=punycode_fqdn,
                unicode_fqdn=fqdn,
                is_valid=True,
            )
            self.session.add(domain)
        else:
            domain.sld = sld
            domain.tld = tld
            domain.punycode_fqdn = punycode_fqdn
            domain.unicode_fqdn = fqdn
            domain.is_valid = True
        self.session.flush()
        return domain


def normalize_generated_domain(domain_name: str, extension: str) -> tuple[str, str, str]:
    """Normalize generated-domain identity into fqdn/sld/tld."""

    sld = normalized_domain_text(domain_name).removeprefix("www.")
    tld = normalized_domain_text(extension)
    if tld.startswith("."):
        tld = tld[1:]
    if "." in sld and tld and sld.endswith(f".{tld}"):
        sld = sld[: -(len(tld) + 1)]
    elif "." in sld and not tld:
        sld, tld = sld.split(".", 1)
    if not sld or not tld or "." in sld:
        raise ValueError("Generated domain must include a valid SLD and extension.")
    return f"{sld}.{tld}", sld, tld


def normalized_domain_text(value: str | None) -> str:
    return str(value or "").strip().lower()


def punycode_domain(fqdn: str) -> str:
    try:
        return fqdn.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Generated domain must include a valid SLD and extension.") from exc


def to_legacy_signal_input(command: GeneratedDomainValuationCommand) -> LegacyOpportunitySignalInput:
    return LegacyOpportunitySignalInput(
        score=command.score,
        grade=command.grade,
        scoring_profile=command.scoring_profile,
        value_estimate=command.value_estimate,
        source_theme=command.source_theme,
        keyword=command.keyword,
        review_bucket=command.review_bucket,
        recommendation=command.recommendation,
        style=command.style,
        risk_notes=command.risk_notes,
    )


def to_classification_input(
    *,
    domain: Domain,
    command: GeneratedDomainValuationCommand,
    input_signal_ids: tuple[UUID, ...],
) -> DomainClassificationInput:
    return DomainClassificationInput(
        domain_id=domain.id,
        fqdn=domain.fqdn,
        sld=domain.sld,
        tld=domain.tld,
        scoring_profile=command.scoring_profile,
        style=command.style,
        niche=command.niche,
        buyer_type=command.buyer_type,
        keyword=command.keyword,
        risk_notes=command.risk_notes,
        rejected_reason=command.rejected_reason,
        input_fact_ids=tuple(),
        input_signal_ids=input_signal_ids,
    )


def build_generated_domain_valuation_request(
    *,
    domain: Domain,
    command: GeneratedDomainValuationCommand,
    classification: ClassificationResult,
    signals: list[DerivedSignal],
) -> DomainValuationRequest:
    signal_refs = tuple(
        EvidenceRef(type="derived_signal", id=str(signal.id), source=signal.signal_key, observed_at=signal.generated_at)
        for signal in signals
    )
    score = clamp_score(command.score) / 100
    liquidity_score = min(1.0, score + tld_liquidity_bonus(domain.tld))
    tokens = text_tuple(classification.tokens_json)
    risk_flag_values = text_tuple(classification.risk_flags_json)
    risk_flags = set(risk_flag_values)
    return DomainValuationRequest(
        domain=DomainRecord(
            id=domain.id,
            fqdn=domain.fqdn,
            sld=domain.sld,
            tld=domain.tld,
            is_valid=domain.is_valid,
        ),
        classification=ClassificationSnapshot(
            classification_result_id=classification.id,
            domain_type=classification.domain_type,
            confidence_score=float(classification.confidence_score),
            business_category=classification.business_category,
            language_code=classification.language_code,
            tokens=tokens,
            risk_flags=risk_flag_values,
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=score,
            search_demand_score=score,
            trend_score=score if command.source_theme else None,
            liquidity_score=liquidity_score,
            evidence_refs=signal_refs,
        ),
        risk_signals=RiskSignals(
            trademark_risk_score=0.72 if "trademark_risk" in risk_flags else None,
            typo_confusion_score=0.72 if "typo_confusion" in risk_flags else None,
            adult_sensitivity_score=0.55 if "adult_or_sensitive" in risk_flags else None,
            legal_notes=command.risk_notes,
        ),
        ecosystem_signals=TldEcosystemSignals(
            tld=domain.tld,
            registry_strength_score=tld_strength(domain.tld),
            aftermarket_liquidity_score=liquidity_score,
            end_user_adoption_score=tld_strength(domain.tld),
            upgrade_target_score=0.82 if domain.tld == "com" else 0.45,
            registered_extension_count=None,
            evidence_refs=signal_refs,
        ),
        algorithm_version=GENERATED_DOMAIN_ALGORITHM_VERSION,
        input_fact_ids=tuple(),
        input_signal_ids=tuple(signal.id for signal in signals),
    )


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value or 0.0)))


def text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def tld_strength(tld: str) -> float:
    return {
        "com": 0.90,
        "ai": 0.72,
        "io": 0.68,
        "org": 0.60,
        "co": 0.58,
        "net": 0.52,
        "app": 0.56,
    }.get(tld.lower(), 0.42)


def tld_liquidity_bonus(tld: str) -> float:
    return {
        "com": 0.08,
        "ai": 0.04,
        "io": 0.03,
        "org": 0.02,
        "net": 0.01,
    }.get(tld.lower(), 0.0)
