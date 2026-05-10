"""Domain classification service built on starter enrichment hints."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from domain_intel.core.enums import DomainType
from domain_intel.db.base import utc_now
from domain_intel.db.models import ClassificationResult
from domain_intel.enrichment.classification import StarterDomainClassificationEngine
from domain_intel.enrichment.contracts import DomainTarget


@dataclass(frozen=True)
class DomainClassificationInput:
    """Inputs needed to classify a domain without mixing facts and signals."""

    domain_id: UUID
    fqdn: str
    sld: str
    tld: str
    scoring_profile: str = ""
    style: str = ""
    niche: str = ""
    buyer_type: str = ""
    keyword: str = ""
    risk_notes: tuple[str, ...] = field(default_factory=tuple)
    rejected_reason: str = ""
    input_fact_ids: tuple[UUID, ...] = field(default_factory=tuple)
    input_signal_ids: tuple[UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DomainClassificationDraft:
    """Write-ready classification result before ORM persistence."""

    domain_type: DomainType
    business_category: str | None
    language_code: str | None
    tokens: tuple[str, ...]
    risk_flags: tuple[str, ...]
    confidence_score: Decimal
    input_fact_ids: tuple[UUID, ...] = field(default_factory=tuple)
    input_signal_ids: tuple[UUID, ...] = field(default_factory=tuple)
    refusal_reason: str | None = None


class DomainClassificationService:
    """Classify domains and persist classification results outside enrichment."""

    def __init__(
        self,
        *,
        algorithm_version: str,
        starter_classifier: StarterDomainClassificationEngine | None = None,
    ) -> None:
        self.algorithm_version = algorithm_version
        self.starter_classifier = starter_classifier or StarterDomainClassificationEngine()

    def build_classification(self, classification_input: DomainClassificationInput) -> DomainClassificationDraft:
        """Build a starter classification draft from domain text and derived inputs."""

        target = DomainTarget(
            domain_id=classification_input.domain_id,
            fqdn=classification_input.fqdn,
            sld=classification_input.sld,
            tld=classification_input.tld,
            punycode_fqdn=classification_input.fqdn,
            unicode_fqdn=classification_input.fqdn,
        )
        hint = self.starter_classifier.classify(target)
        risk_flags = tuple(infer_risk_flags(classification_input))
        domain_type = infer_domain_type(classification_input, hint.mapped_domain_type, risk_flags)
        confidence_score = hint.primary_confidence_score or Decimal("0.5500")
        refusal_reason = None
        if domain_type is DomainType.UNKNOWN:
            confidence_score = min(confidence_score, Decimal("0.4500"))
            refusal_reason = "Starter classifier could not resolve a supported type."

        return DomainClassificationDraft(
            domain_type=domain_type,
            business_category=hint.business_category or classification_input.niche or None,
            language_code="en",
            tokens=tuple(hint.tokens or [classification_input.sld]),
            risk_flags=risk_flags,
            confidence_score=confidence_score,
            input_fact_ids=classification_input.input_fact_ids,
            input_signal_ids=classification_input.input_signal_ids,
            refusal_reason=refusal_reason,
        )

    def upsert_classification(
        self,
        *,
        session: Session,
        domain_id: UUID,
        draft: DomainClassificationDraft,
    ) -> ClassificationResult:
        """Create or update the latest classification row for this service version."""

        row = session.scalar(
            select(ClassificationResult)
            .where(
                ClassificationResult.domain_id == domain_id,
                ClassificationResult.algorithm_version == self.algorithm_version,
            )
            .order_by(desc(ClassificationResult.created_at))
            .limit(1)
        )
        if row is None:
            row = ClassificationResult(domain_id=domain_id)
            session.add(row)

        row.domain_type = draft.domain_type
        row.business_category = draft.business_category
        row.language_code = draft.language_code
        row.tokens_json = list(draft.tokens)
        row.risk_flags_json = list(draft.risk_flags)
        row.confidence_score = draft.confidence_score
        row.algorithm_version = self.algorithm_version
        row.input_fact_ids = list(draft.input_fact_ids)
        row.input_signal_ids = list(draft.input_signal_ids)
        row.refusal_reason = draft.refusal_reason
        row.created_at = utc_now()
        session.flush()
        return row


def infer_domain_type(
    classification_input: DomainClassificationInput,
    starter_type: DomainType | None,
    risk_flags: tuple[str, ...],
) -> DomainType:
    """Resolve backend domain type from starter hints and generated-domain metadata."""

    if "typo_confusion" in risk_flags:
        return DomainType.TYPO_RISK

    values = " ".join(
        [
            classification_input.scoring_profile,
            classification_input.style,
            classification_input.niche,
            classification_input.buyer_type,
            classification_input.keyword,
        ]
    ).lower()
    if "geo" in values or "local" in values:
        return DomainType.GEO
    if "exact" in values:
        return DomainType.EXACT_MATCH
    if "keyword" in values:
        if starter_type in {DomainType.EXACT_MATCH, DomainType.PREMIUM_GENERIC, DomainType.GEO}:
            return starter_type
        return DomainType.KEYWORD_PHRASE
    if "brand" in values or "creative" in values:
        return DomainType.BRANDABLE
    return starter_type or DomainType.UNKNOWN


def infer_risk_flags(classification_input: DomainClassificationInput) -> list[str]:
    """Resolve risk flags from legacy review notes without creating facts."""

    text = " ".join([*classification_input.risk_notes, classification_input.rejected_reason]).lower()
    flags: list[str] = []
    if "trademark" in text or "brand conflict" in text:
        flags.append("trademark_risk")
    if "typo" in text or "confus" in text:
        flags.append("typo_confusion")
    if "adult" in text or "sensitive" in text:
        flags.append("adult_or_sensitive")
    return flags
