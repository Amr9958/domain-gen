"""Unit tests for alert rule evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from domain_intel.services.alert_service import (
    AlertRuleRecord,
    AlertService,
    AlertSubjectSnapshot,
    CreateAlertRuleCommand,
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


class FakeAlertRuleRepository:
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
