"""Sync generated domain opportunities into backend valuation tables."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domain_intel.db.models import (  # noqa: E402
    ClassificationResult,
    DerivedSignal,
    Domain,
)
from domain_intel.db.session import SessionLocal  # noqa: E402
from domain_intel.repositories.valuation_repository import (  # noqa: E402
    PersistValuationRunCommand,
    ValuationRunRepository,
)
from domain_intel.services.classification_service import (  # noqa: E402
    DomainClassificationInput,
    DomainClassificationService,
)
from domain_intel.services.derived_signal_service import (  # noqa: E402
    DerivedSignalService,
    LegacyOpportunitySignalInput,
)
from domain_intel.services.valuation_service import ValuationService  # noqa: E402
from domain_intel.valuation.models import (  # noqa: E402
    ClassificationSnapshot,
    DomainRecord,
    DomainValuationRequest,
    EvidenceRef,
    MarketDemandSignals,
    RiskSignals,
    TldEcosystemSignals,
)
from models import DomainOpportunity, DomainRecommendation  # noqa: E402


BRIDGE_ALGORITHM_VERSION = "generated-domain-bridge-v1"
DEFAULT_INPUT_PATH = PROJECT_ROOT / "signals" / "domain_ideas.jsonl"
LOGGER = logging.getLogger("domain_intel.generated_domain_bridge")


@dataclass(frozen=True)
class SyncSummary:
    """Summary returned by the bridge job."""

    read: int = 0
    synced: int = 0
    skipped_invalid: int = 0
    valued: int = 0
    refused: int = 0
    needs_review: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "read": self.read,
            "synced": self.synced,
            "skipped_invalid": self.skipped_invalid,
            "valued": self.valued,
            "refused": self.refused,
            "needs_review": self.needs_review,
        }


def run_sync(input_path: Path = DEFAULT_INPUT_PATH, *, correlation_id: str | None = None) -> SyncSummary:
    """Run the generated-domain bridge against the configured backend database."""

    correlation_id = correlation_id or str(uuid4())
    LOGGER.info(
        "generated_domain_bridge_started",
        extra={"correlation_id": correlation_id, "input_path": str(input_path)},
    )
    opportunities = list(read_domain_opportunities(input_path))
    summary = SyncSummary(read=len(opportunities))
    if not opportunities:
        LOGGER.info(
            "generated_domain_bridge_noop",
            extra={"correlation_id": correlation_id, "read": summary.read},
        )
        return summary

    valuation_service = ValuationService()
    signal_service = DerivedSignalService(algorithm_version=BRIDGE_ALGORITHM_VERSION)
    classification_service = DomainClassificationService(algorithm_version=BRIDGE_ALGORITHM_VERSION)

    with SessionLocal() as session:
        counts = {
            "synced": 0,
            "skipped_invalid": 0,
            "valued": 0,
            "refused": 0,
            "needs_review": 0,
        }
        for opportunity in opportunities:
            try:
                result_status = sync_opportunity(
                    session=session,
                    opportunity=opportunity,
                    valuation_service=valuation_service,
                    signal_service=signal_service,
                    classification_service=classification_service,
                )
            except ValueError:
                counts["skipped_invalid"] += 1
                LOGGER.warning(
                    "generated_domain_bridge_skipped_invalid",
                    extra={"correlation_id": correlation_id, "domain_name": opportunity.domain_name},
                )
                continue

            counts["synced"] += 1
            counts[result_status] += 1

        session.commit()

    summary = SyncSummary(read=len(opportunities), **counts)
    LOGGER.info(
        "generated_domain_bridge_completed",
        extra={"correlation_id": correlation_id, **summary.as_dict()},
    )
    return summary


def sync_opportunity(
    *,
    session: Session,
    opportunity: DomainOpportunity,
    valuation_service: ValuationService,
    signal_service: DerivedSignalService,
    classification_service: DomainClassificationService,
) -> str:
    """Persist one opportunity and return the stored valuation status bucket."""

    fqdn, sld, tld = normalize_domain(opportunity)
    domain = upsert_domain(session, fqdn=fqdn, sld=sld, tld=tld)
    signals = signal_service.upsert_domain_signals(
        session=session,
        domain_id=domain.id,
        drafts=signal_service.build_legacy_opportunity_drafts(to_legacy_signal_input(opportunity)),
    )
    signal_ids = tuple(signal.id for signal in signals)

    classification_draft = classification_service.build_classification(
        to_classification_input(domain=domain, opportunity=opportunity, input_signal_ids=signal_ids)
    )
    classification = classification_service.upsert_classification(
        session=session,
        domain_id=domain.id,
        draft=classification_draft,
    )
    request = build_valuation_request(
        domain=domain,
        opportunity=opportunity,
        classification=classification,
        signals=signals,
    )
    result = valuation_service.value_domain(request)
    ValuationRunRepository(session).upsert_result(
        PersistValuationRunCommand(
            domain_id=domain.id,
            classification_result_id=classification.id,
            result=result,
            input_signal_ids=signal_ids,
            algorithm_version=BRIDGE_ALGORITHM_VERSION,
        )
    )
    session.flush()
    return result.status.value


def read_domain_opportunities(input_path: Path) -> Iterable[DomainOpportunity]:
    """Read latest generated opportunities from the local JSONL output."""

    if not input_path.exists():
        return []

    latest_rows: dict[str, dict[str, Any]] = {}
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = "||".join(
                [
                    str(row.get("source_theme") or "").strip(),
                    str(row.get("domain_name") or "").strip(),
                    str(row.get("extension") or "").strip(),
                ]
            )
            if key.strip("|"):
                latest_rows[key] = row
    return [domain_opportunity_from_row(row) for row in latest_rows.values()]


def domain_opportunity_from_row(row: dict[str, Any]) -> DomainOpportunity:
    risk_notes = row.get("risk_notes") or []
    if not isinstance(risk_notes, list):
        risk_notes = [str(risk_notes)]

    recommendation_raw = str(row.get("recommendation") or DomainRecommendation.WATCH.value)
    try:
        recommendation = DomainRecommendation(recommendation_raw)
    except ValueError:
        recommendation = DomainRecommendation.WATCH

    return DomainOpportunity(
        domain_name=str(row.get("domain_name") or ""),
        extension=str(row.get("extension") or ""),
        source_theme=str(row.get("source_theme") or ""),
        recommendation=recommendation,
        keyword=str(row.get("keyword") or ""),
        niche=str(row.get("niche") or ""),
        buyer_type=str(row.get("buyer_type") or ""),
        style=str(row.get("style") or ""),
        score=float(row.get("score") or 0),
        review_bucket=str(row.get("review_bucket") or ""),
        scoring_profile=str(row.get("scoring_profile") or ""),
        grade=str(row.get("grade") or ""),
        value_estimate=str(row.get("value_estimate") or ""),
        rationale=str(row.get("rationale") or ""),
        risk_notes=tuple(str(note) for note in risk_notes if str(note).strip()),
        rejected_reason=str(row.get("rejected_reason") or ""),
    )


def normalize_domain(opportunity: DomainOpportunity) -> tuple[str, str, str]:
    sld = opportunity.domain_name.strip().lower().removeprefix("www.")
    extension = opportunity.extension.strip().lower()
    if extension.startswith("."):
        extension = extension[1:]
    if "." in sld and not extension:
        sld, extension = sld.split(".", 1)
    if not sld or not extension or "." in sld:
        raise ValueError("Domain opportunity does not contain a valid SLD and extension.")
    fqdn = f"{sld}.{extension}"
    return fqdn, sld, extension


def upsert_domain(session: Session, *, fqdn: str, sld: str, tld: str) -> Domain:
    domain = session.scalar(select(Domain).where(Domain.fqdn == fqdn))
    punycode_fqdn = fqdn.encode("idna").decode("ascii")
    if domain is None:
        domain = Domain(
            fqdn=fqdn,
            sld=sld,
            tld=tld,
            punycode_fqdn=punycode_fqdn,
            unicode_fqdn=fqdn,
            is_valid=True,
        )
        session.add(domain)
    else:
        domain.sld = sld
        domain.tld = tld
        domain.punycode_fqdn = punycode_fqdn
        domain.unicode_fqdn = fqdn
        domain.is_valid = True
    session.flush()
    return domain


def to_legacy_signal_input(opportunity: DomainOpportunity) -> LegacyOpportunitySignalInput:
    return LegacyOpportunitySignalInput(
        score=opportunity.score,
        grade=opportunity.grade,
        scoring_profile=opportunity.scoring_profile,
        value_estimate=opportunity.value_estimate,
        source_theme=opportunity.source_theme,
        keyword=opportunity.keyword,
        review_bucket=opportunity.review_bucket,
        recommendation=opportunity.recommendation.value,
        style=opportunity.style,
        risk_notes=opportunity.risk_notes,
    )


def to_classification_input(
    *,
    domain: Domain,
    opportunity: DomainOpportunity,
    input_signal_ids: tuple[Any, ...],
) -> DomainClassificationInput:
    return DomainClassificationInput(
        domain_id=domain.id,
        fqdn=domain.fqdn,
        sld=domain.sld,
        tld=domain.tld,
        scoring_profile=opportunity.scoring_profile,
        style=opportunity.style,
        niche=opportunity.niche,
        buyer_type=opportunity.buyer_type,
        keyword=opportunity.keyword,
        risk_notes=opportunity.risk_notes,
        rejected_reason=opportunity.rejected_reason,
        input_fact_ids=tuple(),
        input_signal_ids=input_signal_ids,
    )


def build_valuation_request(
    *,
    domain: Domain,
    opportunity: DomainOpportunity,
    classification: ClassificationResult,
    signals: list[DerivedSignal],
) -> DomainValuationRequest:
    signal_refs = tuple(
        EvidenceRef(type="derived_signal", id=str(signal.id), source=signal.signal_key, observed_at=signal.generated_at)
        for signal in signals
    )
    score = clamp_score(opportunity.score) / 100
    commercial_score = score
    trend_score = score if opportunity.source_theme else None
    liquidity_score = min(1.0, score + tld_liquidity_bonus(domain.tld))
    legal_risk_score = 0.72 if "trademark_risk" in classification.risk_flags_json else None
    typo_score = 0.72 if "typo_confusion" in classification.risk_flags_json else None
    adult_score = 0.55 if "adult_or_sensitive" in classification.risk_flags_json else None

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
            tokens=tuple(str(token) for token in classification.tokens_json),
            risk_flags=tuple(str(flag) for flag in classification.risk_flags_json),
        ),
        market_signals=MarketDemandSignals(
            commercial_intent_score=commercial_score,
            search_demand_score=commercial_score,
            trend_score=trend_score,
            liquidity_score=liquidity_score,
            evidence_refs=signal_refs,
        ),
        risk_signals=RiskSignals(
            trademark_risk_score=legal_risk_score,
            typo_confusion_score=typo_score,
            adult_sensitivity_score=adult_score,
            legal_notes=opportunity.risk_notes,
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
        algorithm_version=BRIDGE_ALGORITHM_VERSION,
        input_fact_ids=tuple(),
        input_signal_ids=tuple(signal.id for signal in signals),
    )


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value or 0.0)))


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync generated domain ideas into backend valuation tables.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to signals/domain_ideas.jsonl.",
    )
    parser.add_argument(
        "--correlation-id",
        default=None,
        help="Optional correlation id for job logs and summary output.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    correlation_id = args.correlation_id or str(uuid4())
    summary = run_sync(args.input, correlation_id=correlation_id).as_dict()
    summary["correlation_id"] = correlation_id
    summary["started_at"] = started_at.isoformat()
    summary["ended_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(summary, ensure_ascii=True))
