"""Alert rule management and evaluation skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Protocol
from uuid import UUID

from domain_intel.core.enums import AlertRuleType, AlertSeverity


@dataclass(frozen=True)
class AlertRuleRecord:
    """Service-level alert rule read model."""

    id: UUID
    organization_id: UUID
    watchlist_id: UUID
    rule_type: str
    is_enabled: bool
    threshold_json: Dict[str, object]
    channel_config_json: Dict[str, object]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CreateAlertRuleCommand:
    """Command for creating an alert rule."""

    organization_id: UUID
    watchlist_id: UUID
    rule_type: str
    is_enabled: bool
    threshold_json: Dict[str, object]
    channel_config_json: Dict[str, object]


@dataclass(frozen=True)
class AlertSubjectSnapshot:
    """Structured event-evaluation input used by background jobs."""

    domain_id: Optional[UUID]
    auction_id: Optional[UUID]
    current_bid_amount: Optional[Decimal]
    currency: Optional[str]
    auction_ends_at: Optional[datetime]
    scores: Dict[str, Decimal]
    upgrade_target_score: Optional[Decimal]
    enrichment_status: Optional[str]
    enrichment_completed_at: Optional[datetime]


@dataclass(frozen=True)
class AlertEventCandidate:
    """Deterministic alert event proposal prior to persistence."""

    event_type: str
    event_key: str
    severity: str
    payload_json: Dict[str, object]
    domain_id: Optional[UUID]
    auction_id: Optional[UUID]


class AlertRuleRepositoryProtocol(Protocol):
    """Persistence boundary for alert rule writes."""

    def create_rule(self, command: CreateAlertRuleCommand) -> AlertRuleRecord:
        """Persist a new alert rule."""


class AlertService:
    """Service for alert-rule creation and rule evaluation skeletons."""

    def __init__(self, repository: AlertRuleRepositoryProtocol) -> None:
        self.repository = repository

    def create_rule(self, command: CreateAlertRuleCommand) -> AlertRuleRecord:
        """Validate and persist an alert rule."""

        self._validate_thresholds(command.rule_type, command.threshold_json)
        return self.repository.create_rule(command)

    def evaluate_rule(
        self,
        rule: AlertRuleRecord,
        subject: AlertSubjectSnapshot,
        evaluation_time: datetime,
    ) -> Optional[AlertEventCandidate]:
        """Evaluate a single alert rule against a structured subject snapshot."""

        if not rule.is_enabled:
            return None

        rule_type = AlertRuleType(rule.rule_type)
        thresholds = rule.threshold_json

        if rule_type == AlertRuleType.AUCTION_ENDING_SOON:
            minutes_before_end = int(thresholds["minutes_before_end"])
            if subject.auction_ends_at is None:
                return None
            remaining = subject.auction_ends_at - evaluation_time
            if timedelta() <= remaining <= timedelta(minutes=minutes_before_end):
                return AlertEventCandidate(
                    event_type=rule.rule_type,
                    event_key=f"{rule.id}:auction-ending-soon:{subject.auction_id}:{subject.auction_ends_at.isoformat()}",
                    severity=AlertSeverity.WARNING.value,
                    payload_json={
                        "minutes_before_end": minutes_before_end,
                        "auction_ends_at": subject.auction_ends_at.isoformat(),
                    },
                    domain_id=subject.domain_id,
                    auction_id=subject.auction_id,
                )
            return None

        if rule_type == AlertRuleType.PRICE_BELOW_THRESHOLD:
            amount = Decimal(str(thresholds["amount"]))
            if subject.current_bid_amount is None:
                return None
            if subject.current_bid_amount <= amount:
                return AlertEventCandidate(
                    event_type=rule.rule_type,
                    event_key=f"{rule.id}:price-below:{subject.auction_id}:{amount}",
                    severity=AlertSeverity.HIGH.value,
                    payload_json={
                        "threshold_amount": str(amount),
                        "current_bid_amount": str(subject.current_bid_amount),
                        "currency": thresholds.get("currency") or subject.currency,
                    },
                    domain_id=subject.domain_id,
                    auction_id=subject.auction_id,
                )
            return None

        if rule_type == AlertRuleType.SCORE_ABOVE_THRESHOLD:
            score_key = str(thresholds["score_key"])
            min_score = Decimal(str(thresholds["min_score"]))
            score_value = subject.scores.get(score_key)
            if score_value is not None and score_value >= min_score:
                return AlertEventCandidate(
                    event_type=rule.rule_type,
                    event_key=f"{rule.id}:score-above:{subject.domain_id}:{score_key}:{score_value}",
                    severity=AlertSeverity.INFO.value,
                    payload_json={
                        "score_key": score_key,
                        "min_score": str(min_score),
                        "score_value": str(score_value),
                    },
                    domain_id=subject.domain_id,
                    auction_id=subject.auction_id,
                )
            return None

        if rule_type == AlertRuleType.STRONG_UPGRADE_TARGET_FOUND:
            min_score = Decimal(str(thresholds.get("min_score", "0.70")))
            if subject.upgrade_target_score is not None and subject.upgrade_target_score >= min_score:
                return AlertEventCandidate(
                    event_type=rule.rule_type,
                    event_key=f"{rule.id}:upgrade-target:{subject.domain_id}:{subject.upgrade_target_score}",
                    severity=AlertSeverity.INFO.value,
                    payload_json={
                        "min_score": str(min_score),
                        "upgrade_target_score": str(subject.upgrade_target_score),
                    },
                    domain_id=subject.domain_id,
                    auction_id=subject.auction_id,
                )
            return None

        if rule_type == AlertRuleType.ENRICHMENT_COMPLETED:
            provider = thresholds.get("provider")
            if subject.enrichment_status == "completed" and subject.enrichment_completed_at is not None:
                return AlertEventCandidate(
                    event_type=rule.rule_type,
                    event_key=f"{rule.id}:enrichment-completed:{subject.domain_id}:{subject.enrichment_completed_at.isoformat()}",
                    severity=AlertSeverity.INFO.value,
                    payload_json={
                        "provider": provider,
                        "completed_at": subject.enrichment_completed_at.isoformat(),
                    },
                    domain_id=subject.domain_id,
                    auction_id=subject.auction_id,
                )
            return None

        return None

    def _validate_thresholds(self, rule_type: str, threshold_json: Dict[str, object]) -> None:
        normalized_rule_type = AlertRuleType(rule_type)
        if normalized_rule_type == AlertRuleType.AUCTION_ENDING_SOON:
            if "minutes_before_end" not in threshold_json:
                raise ValueError("auction_ending_soon rules require minutes_before_end.")
            return
        if normalized_rule_type == AlertRuleType.PRICE_BELOW_THRESHOLD:
            if "amount" not in threshold_json:
                raise ValueError("price_below_threshold rules require amount.")
            return
        if normalized_rule_type == AlertRuleType.SCORE_ABOVE_THRESHOLD:
            if "score_key" not in threshold_json or "min_score" not in threshold_json:
                raise ValueError("score_above_threshold rules require score_key and min_score.")
            return
        if normalized_rule_type == AlertRuleType.STRONG_UPGRADE_TARGET_FOUND:
            return
        if normalized_rule_type == AlertRuleType.ENRICHMENT_COMPLETED:
            return
