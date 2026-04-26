"""Repository for undervalued-auction candidate reads."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from domain_intel.core.enums import AuctionStatus, ConfidenceLevel, ValuationStatus
from domain_intel.db.models import Auction, DerivedSignal, Domain, SourceMarketplace, ValuationRun
from domain_intel.repositories.base import BaseRepository
from domain_intel.services.opportunity_service import (
    OpportunityRepositoryProtocol,
    UndervaluationCandidateInput,
    UndervaluationQuery,
    ValueRangeValue,
)


WHOLESALE_SIGNAL_KEYS = {
    "estimated_wholesale_point",
    "estimated_wholesale_value",
    "wholesale_estimate",
    "estimated_wholesale_min",
    "estimated_wholesale_max",
    "wholesale_estimate_min",
    "wholesale_estimate_max",
    "risk_score",
}


class OpportunityRepository(BaseRepository, OpportunityRepositoryProtocol):
    """SQLAlchemy-backed opportunity repository."""

    def list_candidates(self, query: UndervaluationQuery) -> Tuple[List[UndervaluationCandidateInput], int]:
        """List auction candidates with latest valuation and signal context."""

        criteria = [Auction.status.in_([AuctionStatus.OPEN, AuctionStatus.CLOSING])]
        if query.source:
            criteria.append(SourceMarketplace.code == query.source)
        normalized_tld = _normalize_tld(query.tld)
        if normalized_tld:
            criteria.append(Domain.tld == normalized_tld)

        total = int(
            self.session.scalar(
                select(func.count(Auction.id))
                .join(Auction.domain)
                .join(Auction.marketplace)
                .where(*criteria)
            )
            or 0
        )

        auctions = list(
            self.session.scalars(
                select(Auction)
                .join(Auction.domain)
                .join(Auction.marketplace)
                .options(joinedload(Auction.domain), joinedload(Auction.marketplace))
                .where(*criteria)
                .order_by(Auction.ends_at.asc().nulls_last(), Auction.last_seen_at.desc())
                .limit(query.limit)
                .offset(query.offset)
            ).all()
        )
        if not auctions:
            return [], total

        domain_ids = [auction.domain_id for auction in auctions]
        latest_valuation_subquery = (
            select(
                ValuationRun.domain_id.label("domain_id"),
                func.max(ValuationRun.created_at).label("max_created_at"),
            )
            .where(
                ValuationRun.domain_id.in_(domain_ids),
                ValuationRun.status == ValuationStatus.VALUED,
            )
            .group_by(ValuationRun.domain_id)
            .subquery()
        )

        valuations = list(
            self.session.scalars(
                select(ValuationRun)
                .options(joinedload(ValuationRun.classification_result))
                .join(
                    latest_valuation_subquery,
                    and_(
                        ValuationRun.domain_id == latest_valuation_subquery.c.domain_id,
                        ValuationRun.created_at == latest_valuation_subquery.c.max_created_at,
                    ),
                )
            ).all()
        )
        valuation_by_domain = {valuation.domain_id: valuation for valuation in valuations}

        signals = list(
            self.session.scalars(
                select(DerivedSignal)
                .where(
                    DerivedSignal.domain_id.in_(domain_ids),
                    DerivedSignal.signal_key.in_(WHOLESALE_SIGNAL_KEYS),
                )
                .order_by(DerivedSignal.generated_at.desc())
            ).all()
        )
        signals_by_domain: Dict[object, Dict[str, DerivedSignal]] = defaultdict(dict)
        for signal in signals:
            domain_map = signals_by_domain[signal.domain_id]
            if signal.signal_key not in domain_map:
                domain_map[signal.signal_key] = signal

        candidates: List[UndervaluationCandidateInput] = []
        for auction in auctions:
            valuation = valuation_by_domain.get(auction.domain_id)
            classification = valuation.classification_result if valuation is not None else None
            domain_signals = signals_by_domain.get(auction.domain_id, {})

            candidates.append(
                UndervaluationCandidateInput(
                    auction_id=auction.id,
                    domain_id=auction.domain_id,
                    fqdn=auction.domain.fqdn,
                    tld=auction.domain.tld,
                    marketplace_code=auction.marketplace.code,
                    auction_type=auction.auction_type.value,
                    auction_status=auction.status.value,
                    ends_at=auction.ends_at,
                    current_bid_amount=auction.current_bid_amount,
                    currency=auction.currency,
                    bid_count=auction.bid_count,
                    watchers_count=auction.watchers_count,
                    valuation_status=valuation.status.value if valuation is not None else ValuationStatus.NEEDS_REVIEW.value,
                    confidence_level=(
                        valuation.confidence_level.value if valuation is not None else ConfidenceLevel.LOW.value
                    ),
                    estimated_retail_range=(
                        ValueRangeValue(
                            low=_format_money_amount(valuation.estimated_value_min),
                            high=_format_money_amount(valuation.estimated_value_max),
                            currency=valuation.currency,
                        )
                        if valuation is not None
                        and valuation.estimated_value_min is not None
                        and valuation.estimated_value_max is not None
                        else None
                    ),
                    estimated_wholesale_range=_signal_range(
                        domain_signals,
                        valuation.currency if valuation is not None else (auction.currency or "USD"),
                    ),
                    risk_score=_signal_decimal(domain_signals.get("risk_score")),
                    risk_flags=list(classification.risk_flags_json) if classification is not None else [],
                )
            )

        return candidates, total


def _normalize_tld(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized.startswith("."):
        normalized = normalized[1:]
    return normalized or None


def _signal_range(signals_by_key: Dict[str, DerivedSignal], currency: str) -> Optional[ValueRangeValue]:
    low = _signal_decimal(signals_by_key.get("estimated_wholesale_min")) or _signal_decimal(
        signals_by_key.get("wholesale_estimate_min")
    )
    high = _signal_decimal(signals_by_key.get("estimated_wholesale_max")) or _signal_decimal(
        signals_by_key.get("wholesale_estimate_max")
    )
    point = _signal_decimal(signals_by_key.get("estimated_wholesale_point")) or _signal_decimal(
        signals_by_key.get("estimated_wholesale_value")
    ) or _signal_decimal(signals_by_key.get("wholesale_estimate"))

    if low is None and high is None and point is not None:
        low = point
        high = point
    if low is None or high is None:
        return None
    if low > high:
        low, high = high, low
    return ValueRangeValue(low=_format_money_amount(low), high=_format_money_amount(high), currency=currency)


def _signal_decimal(signal: Optional[DerivedSignal]) -> Optional[Decimal]:
    if signal is None:
        return None
    payload = signal.signal_value_json
    for key in ("score", "value", "amount", "point", "estimate"):
        value = payload.get(key)
        decimal_value = _coerce_decimal(value)
        if decimal_value is not None:
            return decimal_value
    for value in payload.values():
        decimal_value = _coerce_decimal(value)
        if decimal_value is not None:
            return decimal_value
    return None


def _coerce_decimal(value: object) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            return None
    return None


def _format_money_amount(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01")))
