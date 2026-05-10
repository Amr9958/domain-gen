"""Unit tests for alert rule evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from domain_intel.services.alert_service import (
    AlertDeliveryDispatchCandidate,
    AlertDeliveryRecord,
    AlertEventMutationResult,
    AlertEventRecord,
    AlertRuleRecord,
    AlertService,
    AlertSubjectSnapshot,
    CreateAlertRuleCommand,
    RecordAlertDeliveryCommand,
    SlackWebhookAlertDeliveryProvider,
)


def test_auction_ending_soon_rule_emits_event_inside_threshold() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    service = AlertService(FakeAlertRuleRepository())
    rule = AlertRuleRecord(
        id=uuid4(),
        organization_id=uuid4(),
        watchlist_id=uuid4(),
        rule_type="auction_ending_soon",
        is_enabled=True,
        threshold_json={"minutes_before_end": 30},
        channel_config_json={"channels": ["email"]},
        created_at=now,
        updated_at=now,
    )
    subject = AlertSubjectSnapshot(
        domain_id=uuid4(),
        auction_id=uuid4(),
        current_bid_amount=Decimal("125"),
        currency="USD",
        auction_ends_at=now + timedelta(minutes=10),
        scores={},
        upgrade_target_score=None,
        enrichment_status=None,
        enrichment_completed_at=None,
    )

    event = service.evaluate_rule(rule, subject, now)

    assert event is not None
    assert event.event_type == "auction_ending_soon"
    assert event.severity == "warning"


def test_score_above_threshold_requires_expected_keys() -> None:
    service = AlertService(FakeAlertRuleRepository())

    with pytest.raises(ValueError):
        service.create_rule(
            CreateAlertRuleCommand(
                organization_id=uuid4(),
                watchlist_id=uuid4(),
                rule_type="score_above_threshold",
                is_enabled=True,
                threshold_json={"score_key": "investment_score"},
                channel_config_json={},
            )
        )


def test_evaluate_rules_persists_events_and_suppresses_duplicates() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    service = AlertService(repository)
    rule = AlertRuleRecord(
        id=uuid4(),
        organization_id=uuid4(),
        watchlist_id=uuid4(),
        rule_type="price_below_threshold",
        is_enabled=True,
        threshold_json={"amount": "200.00", "currency": "USD"},
        channel_config_json={"channels": ["email"]},
        created_at=now,
        updated_at=now,
    )
    subject = AlertSubjectSnapshot(
        domain_id=uuid4(),
        auction_id=uuid4(),
        current_bid_amount=Decimal("125"),
        currency="USD",
        auction_ends_at=None,
        scores={},
        upgrade_target_score=None,
        enrichment_status=None,
        enrichment_completed_at=None,
    )

    first_result = service.evaluate_rules([rule], subject, now)
    second_result = service.evaluate_rules([rule], subject, now)

    assert len(first_result.created_events) == 1
    assert first_result.suppressed_duplicates == 0
    assert second_result.created_events == []
    assert second_result.suppressed_duplicates == 1


def test_record_delivery_upserts_event_channel_attempts() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    service = AlertService(repository)
    event_id = uuid4()

    first_delivery = service.record_delivery(
        RecordAlertDeliveryCommand(
            alert_event_id=event_id,
            channel="email",
            status="retryable_failure",
            attempted_at=now,
            error_code="smtp_unavailable",
            error_summary="SMTP provider unavailable.",
        )
    )
    second_delivery = service.record_delivery(
        RecordAlertDeliveryCommand(
            alert_event_id=event_id,
            channel="email",
            status="delivered",
            attempted_at=now + timedelta(minutes=5),
        )
    )

    assert second_delivery.id == first_delivery.id
    assert second_delivery.status == "delivered"
    assert second_delivery.attempt_count == 2
    assert second_delivery.delivered_at == now + timedelta(minutes=5)


def test_deliver_event_sends_slack_and_records_delivery() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    slack_client = FakeSlackHttpClient([FakeSlackResponse(200, "ok")])
    service = AlertService(
        repository,
        delivery_providers={"slack": SlackWebhookAlertDeliveryProvider(client=slack_client)},
    )
    rule = _alert_rule(
        now,
        channel_config_json={
            "channels": ["slack"],
            "slack_webhook_url": "https://hooks.slack.test/services/abc",
        },
    )
    event = _alert_event(rule, now)

    deliveries = service.deliver_event(rule, event, now)

    assert len(deliveries) == 1
    assert deliveries[0].channel == "slack"
    assert deliveries[0].status == "delivered"
    assert slack_client.posts[0]["url"] == "https://hooks.slack.test/services/abc"
    assert slack_client.posts[0]["json"]["text"] == "[High] Price Below Threshold"
    assert repository.deliveries_by_channel[(event.id, "slack")].status == "delivered"


def test_deliver_event_records_terminal_failure_for_missing_slack_webhook() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    service = AlertService(
        repository,
        delivery_providers={"slack": SlackWebhookAlertDeliveryProvider(client=FakeSlackHttpClient([]))},
    )
    rule = _alert_rule(now, channel_config_json={"channels": ["slack"]})
    event = _alert_event(rule, now)

    deliveries = service.deliver_event(rule, event, now)

    assert deliveries[0].status == "terminal_failure"
    assert deliveries[0].error_code == "missing_slack_webhook_url"


def test_deliver_event_records_retryable_failure_for_slack_5xx() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    slack_client = FakeSlackHttpClient([FakeSlackResponse(503, "temporarily unavailable")])
    service = AlertService(
        repository,
        delivery_providers={"slack": SlackWebhookAlertDeliveryProvider(client=slack_client)},
    )
    rule = _alert_rule(
        now,
        channel_config_json={
            "channels": ["slack"],
            "slack": {"webhook_url": "https://hooks.slack.test/services/abc"},
        },
    )
    event = _alert_event(rule, now)

    deliveries = service.deliver_event(rule, event, now)

    assert deliveries[0].status == "retryable_failure"
    assert deliveries[0].error_code == "slack_http_503"
    assert deliveries[0].error_summary == "temporarily unavailable"


def test_deliver_event_records_terminal_failure_for_unsupported_channel() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    service = AlertService(repository)
    rule = _alert_rule(now, channel_config_json={"channels": ["email"]})
    event = _alert_event(rule, now)

    deliveries = service.deliver_event(rule, event, now)

    assert deliveries[0].channel == "email"
    assert deliveries[0].status == "terminal_failure"
    assert deliveries[0].error_code == "unsupported_alert_channel"


def test_dispatch_pending_deliveries_attempts_new_and_retryable_channels_only() -> None:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    repository = FakeAlertRuleRepository()
    slack_client = FakeSlackHttpClient([FakeSlackResponse(200, "ok"), FakeSlackResponse(200, "ok")])
    service = AlertService(
        repository,
        delivery_providers={"slack": SlackWebhookAlertDeliveryProvider(client=slack_client)},
    )
    rule = _alert_rule(
        now,
        channel_config_json={
            "channels": ["slack"],
            "slack_webhook_url": "https://hooks.slack.test/services/abc",
        },
    )
    new_event = _alert_event(rule, now)
    retryable_event = _alert_event(rule, now)
    delivered_event = _alert_event(rule, now)
    repository.delivery_candidates = [
        AlertDeliveryDispatchCandidate(rule=rule, event=new_event, deliveries_by_channel={}),
        AlertDeliveryDispatchCandidate(
            rule=rule,
            event=retryable_event,
            deliveries_by_channel={
                "slack": AlertDeliveryRecord(
                    id=uuid4(),
                    alert_event_id=retryable_event.id,
                    channel="slack",
                    status="retryable_failure",
                    attempt_count=1,
                    last_attempt_at=now - timedelta(minutes=5),
                    delivered_at=None,
                    error_code="slack_http_503",
                    error_summary="temporarily unavailable",
                )
            },
        ),
        AlertDeliveryDispatchCandidate(
            rule=rule,
            event=delivered_event,
            deliveries_by_channel={
                "slack": AlertDeliveryRecord(
                    id=uuid4(),
                    alert_event_id=delivered_event.id,
                    channel="slack",
                    status="delivered",
                    attempt_count=1,
                    last_attempt_at=now - timedelta(minutes=5),
                    delivered_at=now - timedelta(minutes=5),
                    error_code=None,
                    error_summary=None,
                )
            },
        ),
    ]

    result = service.dispatch_pending_deliveries(now, limit=10)

    assert result.attempted == 2
    assert result.delivered == 2
    assert result.retryable_failures == 0
    assert result.terminal_failures == 0
    assert result.skipped == 1
    assert len(slack_client.posts) == 2


def _alert_rule(now: datetime, channel_config_json: dict[str, object]) -> AlertRuleRecord:
    return AlertRuleRecord(
        id=uuid4(),
        organization_id=uuid4(),
        watchlist_id=uuid4(),
        rule_type="price_below_threshold",
        is_enabled=True,
        threshold_json={"amount": "200.00", "currency": "USD"},
        channel_config_json=channel_config_json,
        created_at=now,
        updated_at=now,
    )


def _alert_event(rule: AlertRuleRecord, now: datetime) -> AlertEventRecord:
    return AlertEventRecord(
        id=uuid4(),
        alert_rule_id=rule.id,
        domain_id=uuid4(),
        auction_id=uuid4(),
        event_type="price_below_threshold",
        event_key=f"{rule.id}:price-below:test",
        severity="high",
        payload_json={"threshold_amount": "200.00", "current_bid_amount": "125.00", "currency": "USD"},
        created_at=now,
    )


class FakeSlackResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class FakeSlackHttpClient:
    def __init__(self, responses: list[FakeSlackResponse]) -> None:
        self.responses = responses
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, json: dict[str, object]) -> FakeSlackResponse:
        self.posts.append({"url": url, "json": json})
        return self.responses.pop(0)


class FakeAlertRuleRepository:
    def __init__(self) -> None:
        self.events_by_key = {}
        self.deliveries_by_channel = {}
        self.delivery_candidates = []

    def create_rule(self, command: CreateAlertRuleCommand) -> AlertRuleRecord:
        now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        return AlertRuleRecord(
            id=uuid4(),
            organization_id=command.organization_id,
            watchlist_id=command.watchlist_id,
            rule_type=command.rule_type,
            is_enabled=command.is_enabled,
            threshold_json=command.threshold_json,
            channel_config_json=command.channel_config_json,
            created_at=now,
            updated_at=now,
        )

    def upsert_event(self, rule, candidate, evaluation_time) -> AlertEventMutationResult:
        key = (rule.id, candidate.event_key)
        if key in self.events_by_key:
            return AlertEventMutationResult(event=self.events_by_key[key], created=False)
        event = AlertEventRecord(
            id=uuid4(),
            alert_rule_id=rule.id,
            domain_id=candidate.domain_id,
            auction_id=candidate.auction_id,
            event_type=candidate.event_type,
            event_key=candidate.event_key,
            severity=candidate.severity,
            payload_json=candidate.payload_json,
            created_at=evaluation_time,
        )
        self.events_by_key[key] = event
        return AlertEventMutationResult(event=event, created=True)

    def upsert_delivery(self, command: RecordAlertDeliveryCommand) -> AlertDeliveryRecord:
        key = (command.alert_event_id, command.channel)
        previous = self.deliveries_by_channel.get(key)
        delivery = AlertDeliveryRecord(
            id=previous.id if previous else uuid4(),
            alert_event_id=command.alert_event_id,
            channel=command.channel,
            status=command.status,
            attempt_count=(previous.attempt_count if previous else 0) + 1,
            last_attempt_at=command.attempted_at,
            delivered_at=command.attempted_at if command.status == "delivered" else None,
            error_code=command.error_code,
            error_summary=command.error_summary,
        )
        self.deliveries_by_channel[key] = delivery
        return delivery

    def list_delivery_candidates(self, limit: int = 100) -> list[AlertDeliveryDispatchCandidate]:
        return self.delivery_candidates[:limit]
