"""Alert rule management and evaluation skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol
from uuid import UUID

import httpx

from domain_intel.core.enums import AlertRuleType, AlertSeverity


ALERT_RULE_REQUIRED_THRESHOLD_KEYS = {
    AlertRuleType.AUCTION_ENDING_SOON: ("minutes_before_end",),
    AlertRuleType.PRICE_BELOW_THRESHOLD: ("amount",),
    AlertRuleType.SCORE_ABOVE_THRESHOLD: ("score_key", "min_score"),
}
ALERT_RULE_DEFAULT_THRESHOLDS = {
    AlertRuleType.STRONG_UPGRADE_TARGET_FOUND: {"min_score": "0.70"},
}
ALERT_DELIVERY_STATUSES = {"delivered", "retryable_failure", "terminal_failure"}
SLACK_ALERT_CHANNEL = "slack"


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


@dataclass(frozen=True)
class AlertEventRecord:
    """Persisted alert event read model."""

    id: UUID
    alert_rule_id: UUID
    domain_id: Optional[UUID]
    auction_id: Optional[UUID]
    event_type: str
    event_key: str
    severity: str
    payload_json: Dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class AlertEventMutationResult:
    """Result of deduplicated alert event persistence."""

    event: AlertEventRecord
    created: bool


@dataclass(frozen=True)
class AlertEvaluationResult:
    """Batch alert evaluation result."""

    created_events: List[AlertEventRecord]
    suppressed_duplicates: int


@dataclass(frozen=True)
class RecordAlertDeliveryCommand:
    """Command for recording one alert delivery attempt."""

    alert_event_id: UUID
    channel: str
    status: str
    attempted_at: datetime
    error_code: Optional[str] = None
    error_summary: Optional[str] = None


@dataclass(frozen=True)
class AlertDeliveryRecord:
    """Persisted alert delivery read model."""

    id: UUID
    alert_event_id: UUID
    channel: str
    status: str
    attempt_count: int
    last_attempt_at: Optional[datetime]
    delivered_at: Optional[datetime]
    error_code: Optional[str]
    error_summary: Optional[str]


@dataclass(frozen=True)
class AlertDeliveryDispatchCandidate:
    """Persisted event plus existing delivery state for dispatch jobs."""

    rule: AlertRuleRecord
    event: AlertEventRecord
    deliveries_by_channel: Dict[str, AlertDeliveryRecord]


@dataclass(frozen=True)
class AlertDeliveryDispatchResult:
    """Summary returned by alert delivery dispatch jobs."""

    attempted: int
    delivered: int
    retryable_failures: int
    terminal_failures: int
    skipped: int


@dataclass(frozen=True)
class AlertDeliveryProviderResult:
    """Provider-level delivery result before persistence."""

    channel: str
    status: str
    error_code: Optional[str] = None
    error_summary: Optional[str] = None


class AlertDeliveryProvider(Protocol):
    """Provider boundary for sending an alert event through one channel."""

    channel: str

    def deliver(self, rule: AlertRuleRecord, event: AlertEventRecord) -> AlertDeliveryProviderResult:
        """Send the event and return a persistence-ready delivery result."""


class SlackWebhookAlertDeliveryProvider:
    """Send alert events to Slack through an incoming webhook URL."""

    channel = SLACK_ALERT_CHANNEL

    def __init__(self, client: httpx.Client | None = None, timeout_seconds: float = 10.0) -> None:
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def deliver(self, rule: AlertRuleRecord, event: AlertEventRecord) -> AlertDeliveryProviderResult:
        webhook_url = _slack_webhook_url(rule.channel_config_json)
        if not webhook_url:
            return AlertDeliveryProviderResult(
                channel=self.channel,
                status="terminal_failure",
                error_code="missing_slack_webhook_url",
                error_summary="Slack channel requires slack_webhook_url or slack.webhook_url.",
            )

        payload = _build_slack_payload(rule, event)
        try:
            response = self.client.post(webhook_url, json=payload)
        except httpx.TimeoutException as exc:
            return AlertDeliveryProviderResult(
                channel=self.channel,
                status="retryable_failure",
                error_code="slack_timeout",
                error_summary=str(exc),
            )
        except httpx.HTTPError as exc:
            return AlertDeliveryProviderResult(
                channel=self.channel,
                status="retryable_failure",
                error_code="slack_http_error",
                error_summary=str(exc),
            )

        status_code = getattr(response, "status_code", 0)
        if 200 <= int(status_code) < 300:
            return AlertDeliveryProviderResult(channel=self.channel, status="delivered")
        if int(status_code) in {408, 425, 429, 500, 502, 503, 504}:
            return AlertDeliveryProviderResult(
                channel=self.channel,
                status="retryable_failure",
                error_code=f"slack_http_{status_code}",
                error_summary=_safe_response_text(response),
            )
        return AlertDeliveryProviderResult(
            channel=self.channel,
            status="terminal_failure",
            error_code=f"slack_http_{status_code}",
            error_summary=_safe_response_text(response),
        )


class AlertRuleRepositoryProtocol(Protocol):
    """Persistence boundary for alert rule writes."""

    def create_rule(self, command: CreateAlertRuleCommand) -> AlertRuleRecord:
        """Persist a new alert rule."""

    def upsert_event(
        self,
        rule: AlertRuleRecord,
        candidate: AlertEventCandidate,
        evaluation_time: datetime,
    ) -> AlertEventMutationResult:
        """Persist a deduplicated alert event."""

    def upsert_delivery(self, command: RecordAlertDeliveryCommand) -> AlertDeliveryRecord:
        """Persist or update a delivery attempt."""

    def list_delivery_candidates(self, limit: int = 100) -> list[AlertDeliveryDispatchCandidate]:
        """Load persisted alert events that may need channel delivery."""


class AlertService:
    """Service for alert-rule creation and rule evaluation skeletons."""

    def __init__(
        self,
        repository: AlertRuleRepositoryProtocol,
        delivery_providers: Mapping[str, AlertDeliveryProvider] | None = None,
    ) -> None:
        self.repository = repository
        self.delivery_providers = dict(delivery_providers or {})

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
            min_score = Decimal(str(thresholds.get("min_score", ALERT_RULE_DEFAULT_THRESHOLDS[rule_type]["min_score"])))
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

    def evaluate_rules(
        self,
        rules: Iterable[AlertRuleRecord],
        subject: AlertSubjectSnapshot,
        evaluation_time: datetime,
    ) -> AlertEvaluationResult:
        """Evaluate rules and persist newly-created alert events."""

        created_events: List[AlertEventRecord] = []
        suppressed_duplicates = 0
        for rule in rules:
            candidate = self.evaluate_rule(rule, subject, evaluation_time)
            if candidate is None:
                continue
            result = self.repository.upsert_event(rule, candidate, evaluation_time)
            if result.created:
                created_events.append(result.event)
            else:
                suppressed_duplicates += 1
        return AlertEvaluationResult(created_events=created_events, suppressed_duplicates=suppressed_duplicates)

    def record_delivery(self, command: RecordAlertDeliveryCommand) -> AlertDeliveryRecord:
        """Record a delivery outcome for an alert event."""

        if command.status not in ALERT_DELIVERY_STATUSES:
            raise ValueError(f"Unsupported alert delivery status: {command.status}.")
        if not command.channel.strip():
            raise ValueError("Alert delivery channel is required.")
        return self.repository.upsert_delivery(command)

    def deliver_event(
        self,
        rule: AlertRuleRecord,
        event: AlertEventRecord,
        attempted_at: datetime,
        existing_deliveries_by_channel: Mapping[str, AlertDeliveryRecord] | None = None,
        max_attempts: int = 3,
    ) -> list[AlertDeliveryRecord]:
        """Deliver an already-persisted alert event through configured channels."""

        deliveries: list[AlertDeliveryRecord] = []
        existing_deliveries_by_channel = dict(existing_deliveries_by_channel or {})
        for channel in _configured_alert_channels(rule.channel_config_json):
            existing_delivery = existing_deliveries_by_channel.get(channel)
            if not _should_attempt_delivery(existing_delivery, max_attempts=max_attempts):
                continue
            provider = self.delivery_providers.get(channel)
            if provider is None:
                result = AlertDeliveryProviderResult(
                    channel=channel,
                    status="terminal_failure",
                    error_code="unsupported_alert_channel",
                    error_summary=f"Alert channel is not supported: {channel}.",
                )
            else:
                result = provider.deliver(rule, event)
            deliveries.append(
                self.record_delivery(
                    RecordAlertDeliveryCommand(
                        alert_event_id=event.id,
                        channel=result.channel,
                        status=result.status,
                        attempted_at=attempted_at,
                        error_code=result.error_code,
                        error_summary=result.error_summary,
                    )
                )
            )
        return deliveries

    def dispatch_pending_deliveries(
        self,
        attempted_at: datetime,
        limit: int = 100,
        max_attempts: int = 3,
    ) -> AlertDeliveryDispatchResult:
        """Dispatch pending alert deliveries while keeping event persistence separate."""

        attempted = delivered = retryable_failures = terminal_failures = skipped = 0
        for candidate in self.repository.list_delivery_candidates(limit=limit):
            channel_count = len(_configured_alert_channels(candidate.rule.channel_config_json))
            deliveries = self.deliver_event(
                candidate.rule,
                candidate.event,
                attempted_at,
                existing_deliveries_by_channel=candidate.deliveries_by_channel,
                max_attempts=max_attempts,
            )
            attempted += len(deliveries)
            skipped += max(0, channel_count - len(deliveries))
            for delivery in deliveries:
                if delivery.status == "delivered":
                    delivered += 1
                elif delivery.status == "retryable_failure":
                    retryable_failures += 1
                elif delivery.status == "terminal_failure":
                    terminal_failures += 1
        return AlertDeliveryDispatchResult(
            attempted=attempted,
            delivered=delivered,
            retryable_failures=retryable_failures,
            terminal_failures=terminal_failures,
            skipped=skipped,
        )

    def _validate_thresholds(self, rule_type: str, threshold_json: Dict[str, object]) -> None:
        normalized_rule_type = AlertRuleType(rule_type)
        for key in ALERT_RULE_REQUIRED_THRESHOLD_KEYS.get(normalized_rule_type, ()):
            if key not in threshold_json:
                raise ValueError(f"{normalized_rule_type.value} rules require {key}.")


def _configured_alert_channels(channel_config_json: Mapping[str, object]) -> list[str]:
    raw_channels = channel_config_json.get("channels", [])
    if isinstance(raw_channels, str):
        raw_channels = [raw_channels]
    if not isinstance(raw_channels, list):
        return []
    channels: list[str] = []
    for raw_channel in raw_channels:
        channel = str(raw_channel or "").strip().lower()
        if channel and channel not in channels:
            channels.append(channel)
    return channels


def _slack_webhook_url(channel_config_json: Mapping[str, object]) -> str:
    direct_value = channel_config_json.get("slack_webhook_url")
    if isinstance(direct_value, str) and direct_value.strip():
        return direct_value.strip()
    nested_value = channel_config_json.get("slack")
    if isinstance(nested_value, Mapping):
        webhook_url = nested_value.get("webhook_url")
        if isinstance(webhook_url, str) and webhook_url.strip():
            return webhook_url.strip()
    return ""


def _build_slack_payload(rule: AlertRuleRecord, event: AlertEventRecord) -> dict[str, Any]:
    severity = event.severity.replace("_", " ").title()
    event_type = event.event_type.replace("_", " ").title()
    text = f"[{severity}] {event_type}"
    fields = {
        "rule_type": rule.rule_type,
        "event_key": event.event_key,
        "domain_id": str(event.domain_id) if event.domain_id else "",
        "auction_id": str(event.auction_id) if event.auction_id else "",
        **{key: str(value) for key, value in event.payload_json.items()},
    }
    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{text}*"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{key}*\n{value}"}
                    for key, value in fields.items()
                    if value
                ][:10],
            },
        ],
    }


def _safe_response_text(response: object) -> str:
    text = getattr(response, "text", "")
    if not isinstance(text, str):
        return ""
    return text[:500]


def _should_attempt_delivery(delivery: AlertDeliveryRecord | None, max_attempts: int) -> bool:
    if delivery is None:
        return True
    if delivery.status == "retryable_failure" and delivery.attempt_count < max_attempts:
        return True
    return False
