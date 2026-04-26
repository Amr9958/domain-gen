"""Undervalued-auction screening service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Protocol, Tuple
from uuid import UUID

from domain_intel.core.enums import ConfidenceLevel, UndervaluationStatus, ValuationStatus
from domain_intel.services.shared_types import MoneyValue


@dataclass(frozen=True)
class ValueRangeValue:
    """Service-safe range value using decimal strings."""

    low: str
    high: str
    currency: str


@dataclass(frozen=True)
class UndervaluationCandidateInput:
    """Structured candidate input from repositories."""

    auction_id: UUID
    domain_id: UUID
    fqdn: str
    tld: str
    marketplace_code: str
    auction_type: str
    auction_status: str
    ends_at: Optional[datetime]
    current_bid_amount: Optional[Decimal]
    currency: Optional[str]
    bid_count: Optional[int]
    watchers_count: Optional[int]
    valuation_status: str
    confidence_level: str
    estimated_retail_range: Optional[ValueRangeValue]
    estimated_wholesale_range: Optional[ValueRangeValue]
    risk_score: Optional[Decimal]
    risk_flags: List[dict]


@dataclass(frozen=True)
class UndervaluationPolicy:
    """Thresholds for deterministic opportunity screening."""

    min_confidence_level: str = ConfidenceLevel.MEDIUM.value
    max_risk_score: Decimal = Decimal("0.35")
    max_bid_to_wholesale_ratio: Decimal = Decimal("1.00")
    max_bid_to_retail_ratio: Decimal = Decimal("0.35")


@dataclass(frozen=True)
class UndervaluationQuery:
    """Query parameters for listing opportunity candidates."""

    source: Optional[str] = None
    tld: Optional[str] = None
    limit: int = 50
    offset: int = 0
    include_rejected: bool = False
    policy: UndervaluationPolicy = UndervaluationPolicy()


@dataclass(frozen=True)
class UndervaluedAuctionRecord:
    """Service read model for dashboard opportunity cards."""

    auction_id: UUID
    domain_id: UUID
    fqdn: str
    marketplace_code: str
    auction_type: str
    auction_status: str
    ends_at: Optional[datetime]
    current_bid: Optional[MoneyValue]
    estimated_wholesale_range: Optional[ValueRangeValue]
    estimated_retail_range: Optional[ValueRangeValue]
    bid_to_estimated_wholesale_ratio: Optional[str]
    bid_to_estimated_retail_ratio: Optional[str]
    confidence_level: str
    risk_score: Optional[str]
    risk_flags: List[dict]
    status: str
    reasons: List[str]


@dataclass(frozen=True)
class UndervaluedAuctionPage:
    """Paginated opportunity result."""

    items: List[UndervaluedAuctionRecord]
    total: int
    limit: int
    offset: int


class OpportunityRepositoryProtocol(Protocol):
    """Persistence boundary for opportunity screening reads."""

    def list_candidates(self, query: UndervaluationQuery) -> Tuple[List[UndervaluationCandidateInput], int]:
        """List structured opportunity candidates and total count."""


class OpportunityService:
    """Service for deterministic undervalued-auction screening."""

    def __init__(self, repository: OpportunityRepositoryProtocol) -> None:
        self.repository = repository

    def list_undervalued_auctions(self, query: UndervaluationQuery) -> UndervaluedAuctionPage:
        """Return candidate opportunity records for dashboard use."""

        candidates, total = self.repository.list_candidates(query)
        items = [self.assess_candidate(candidate, query.policy) for candidate in candidates]
        if not query.include_rejected:
            items = [item for item in items if item.status == UndervaluationStatus.CANDIDATE.value]
        return UndervaluedAuctionPage(items=items, total=total, limit=query.limit, offset=query.offset)

    def assess_candidate(
        self,
        candidate: UndervaluationCandidateInput,
        policy: UndervaluationPolicy,
    ) -> UndervaluedAuctionRecord:
        """Assess one candidate using explicit confidence and risk gates."""

        reasons: List[str] = []
        if candidate.valuation_status != ValuationStatus.VALUED.value:
            reasons.append("No valued retail estimate is available.")
            return self._record(candidate, None, None, UndervaluationStatus.INSUFFICIENT_DATA.value, reasons)

        if candidate.current_bid_amount is None or candidate.currency is None:
            reasons.append("Current bid is missing.")
            return self._record(candidate, None, None, UndervaluationStatus.INSUFFICIENT_DATA.value, reasons)

        retail_point = _range_midpoint(candidate.estimated_retail_range)
        wholesale_point = _range_midpoint(candidate.estimated_wholesale_range)
        if retail_point is None or wholesale_point is None:
            reasons.append("Both wholesale and retail estimates are required for the skeleton screen.")
            return self._record(candidate, None, None, UndervaluationStatus.INSUFFICIENT_DATA.value, reasons)

        if _confidence_rank(candidate.confidence_level) < _confidence_rank(policy.min_confidence_level):
            reasons.append(
                f"Confidence {candidate.confidence_level} is below required {policy.min_confidence_level}."
            )

        legal_risk = any("trademark" in str(flag).lower() or "legal" in str(flag).lower() for flag in candidate.risk_flags)
        if legal_risk:
            reasons.append("Legal or trademark risk is present.")

        if candidate.risk_score is not None and candidate.risk_score > policy.max_risk_score:
            reasons.append(
                f"Risk score {candidate.risk_score.quantize(Decimal('0.01'))} exceeds {policy.max_risk_score.quantize(Decimal('0.01'))}."
            )

        bid_to_wholesale_ratio = candidate.current_bid_amount / wholesale_point
        bid_to_retail_ratio = candidate.current_bid_amount / retail_point

        if bid_to_wholesale_ratio > policy.max_bid_to_wholesale_ratio:
            reasons.append(
                f"Current bid is above the allowed wholesale ratio of {policy.max_bid_to_wholesale_ratio}."
            )
        if bid_to_retail_ratio > policy.max_bid_to_retail_ratio:
            reasons.append(
                f"Current bid is above the allowed retail ratio of {policy.max_bid_to_retail_ratio}."
            )

        status = UndervaluationStatus.CANDIDATE.value if not reasons else UndervaluationStatus.REJECTED.value
        if status == UndervaluationStatus.CANDIDATE.value:
            reasons.append("Current bid sits below configured wholesale and retail thresholds.")

        return self._record(
            candidate,
            bid_to_wholesale_ratio,
            bid_to_retail_ratio,
            status,
            reasons,
        )

    def _record(
        self,
        candidate: UndervaluationCandidateInput,
        bid_to_wholesale_ratio: Optional[Decimal],
        bid_to_retail_ratio: Optional[Decimal],
        status: str,
        reasons: List[str],
    ) -> UndervaluedAuctionRecord:
        return UndervaluedAuctionRecord(
            auction_id=candidate.auction_id,
            domain_id=candidate.domain_id,
            fqdn=candidate.fqdn,
            marketplace_code=candidate.marketplace_code,
            auction_type=candidate.auction_type,
            auction_status=candidate.auction_status,
            ends_at=candidate.ends_at,
            current_bid=_money_value(candidate.current_bid_amount, candidate.currency),
            estimated_wholesale_range=candidate.estimated_wholesale_range,
            estimated_retail_range=candidate.estimated_retail_range,
            bid_to_estimated_wholesale_ratio=_format_ratio(bid_to_wholesale_ratio),
            bid_to_estimated_retail_ratio=_format_ratio(bid_to_retail_ratio),
            confidence_level=candidate.confidence_level,
            risk_score=_format_ratio(candidate.risk_score),
            risk_flags=candidate.risk_flags,
            status=status,
            reasons=reasons,
        )


def _confidence_rank(value: str) -> int:
    mapping = {
        ConfidenceLevel.LOW.value: 1,
        ConfidenceLevel.MEDIUM.value: 2,
        ConfidenceLevel.HIGH.value: 3,
    }
    return mapping.get(value, 0)


def _money_value(amount: Optional[Decimal], currency: Optional[str]) -> Optional[MoneyValue]:
    if amount is None or not currency:
        return None
    normalized_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return MoneyValue(amount=str(normalized_amount), currency=currency)


def _range_midpoint(value_range: Optional[ValueRangeValue]) -> Optional[Decimal]:
    if value_range is None:
        return None
    return (Decimal(value_range.low) + Decimal(value_range.high)) / Decimal("2")


def _format_ratio(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
