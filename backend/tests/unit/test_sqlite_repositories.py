"""SQLite-backed repository tests for workflow and reporting reads."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator
from uuid import UUID, uuid4

from sqlalchemy import JSON, Text, create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from domain_intel.core.enums import (
    AuctionStatus,
    AuctionType,
    ConfidenceLevel,
    DomainType,
    ValuationStatus,
    ValueTier,
)
from domain_intel.db.base import Base
from domain_intel.db.models import (
    AIExplanation,
    AlertRule,
    Auction,
    ClassificationResult,
    DerivedSignal,
    Domain,
    Organization,
    OrganizationMember,
    SourceMarketplace,
    User,
    ValuationReasonCode,
    ValuationRun,
    VerifiedFact,
    Watchlist,
)
from domain_intel.repositories.opportunity_repository import OpportunityRepository
from domain_intel.repositories.report_repository import AppraisalReportRepository
from domain_intel.repositories.workflow_repository import AlertRuleRepository, WatchlistRepository
from domain_intel.services.alert_service import (
    AlertEventCandidate,
    CreateAlertRuleCommand,
    RecordAlertDeliveryCommand,
)
from domain_intel.services.opportunity_service import UndervaluationQuery
from domain_intel.services.report_service import GenerateAppraisalReportCommand
from domain_intel.services.watchlist_service import (
    AddWatchlistItemCommand,
    CreateWatchlistCommand,
    RemoveWatchlistItemCommand,
)


NOW = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)


class SqliteUUIDArray(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps([str(item) for item in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else json.loads(value)
        return [item if isinstance(item, UUID) else UUID(str(item)) for item in raw_items]


def test_watchlist_repository_creates_lists_and_removes_items() -> None:
    with _sqlite_session() as session:
        organization, owner = _create_org_member(session)
        outsider = _create_user(session, "outsider")
        marketplace = _create_marketplace(session, "dynadot")
        domain = _create_domain(session, "atlasai.com")
        auction = _create_auction(session, marketplace, domain)
        session.commit()

        repository = WatchlistRepository(session)
        watchlist = repository.create_watchlist(
            CreateWatchlistCommand(
                organization_id=organization.id,
                owner_user_id=owner.id,
                name="Investor Shortlist",
                visibility="private",
            )
        )
        item = repository.add_item(
            AddWatchlistItemCommand(
                watchlist_id=watchlist.id,
                created_by_user_id=owner.id,
                domain_id=domain.id,
                auction_id=auction.id,
                notes="Watch before close.",
            )
        )

        listed = repository.list_watchlists(organization.id, owner.id)
        blocked = repository.list_watchlists(organization.id, outsider.id)

        assert blocked == []
        assert len(listed) == 1
        assert listed[0].item_count == 1
        assert listed[0].items[0].id == item.id
        assert listed[0].items[0].domain_id == domain.id
        assert listed[0].items[0].auction_id == auction.id

        removed = repository.remove_item(
            RemoveWatchlistItemCommand(
                watchlist_id=watchlist.id,
                watchlist_item_id=item.id,
                organization_id=organization.id,
                actor_user_id=owner.id,
            )
        )

        assert removed is True
        assert repository.list_watchlists(organization.id, owner.id)[0].items == []


def test_alert_repository_deduplicates_events_and_updates_deliveries() -> None:
    with _sqlite_session() as session:
        organization, owner = _create_org_member(session)
        watchlist = _create_watchlist_model(session, organization, owner)
        domain = _create_domain(session, "atlasai.com")
        marketplace = _create_marketplace(session, "dynadot")
        auction = _create_auction(session, marketplace, domain)
        session.commit()

        repository = AlertRuleRepository(session)
        rule = repository.create_rule(
            CreateAlertRuleCommand(
                organization_id=organization.id,
                watchlist_id=watchlist.id,
                rule_type="price_below_threshold",
                is_enabled=True,
                threshold_json={"amount": "500", "currency": "USD"},
                channel_config_json={"channels": ["slack"], "slack_webhook_url": "https://example.test/hook"},
            )
        )
        disabled_rule = repository.create_rule(
            CreateAlertRuleCommand(
                organization_id=organization.id,
                watchlist_id=watchlist.id,
                rule_type="auction_ending_soon",
                is_enabled=False,
                threshold_json={"minutes_before_end": 60},
                channel_config_json={"channels": ["slack"]},
            )
        )
        candidate = AlertEventCandidate(
            event_type="price_below_threshold",
            event_key=f"{rule.id}:price-below:{auction.id}:500",
            severity="high",
            payload_json={"current_bid_amount": "300", "threshold_amount": "500"},
            domain_id=domain.id,
            auction_id=auction.id,
        )

        created = repository.upsert_event(rule, candidate, NOW)
        duplicate = repository.upsert_event(rule, candidate, NOW + timedelta(minutes=1))
        repository.upsert_event(
            disabled_rule,
            AlertEventCandidate(
                event_type="auction_ending_soon",
                event_key=f"{disabled_rule.id}:ending:{auction.id}",
                severity="warning",
                payload_json={"minutes_before_end": 60},
                domain_id=domain.id,
                auction_id=auction.id,
            ),
            NOW,
        )
        first_delivery = repository.upsert_delivery(
            RecordAlertDeliveryCommand(
                alert_event_id=created.event.id,
                channel="slack",
                status="retryable_failure",
                attempted_at=NOW,
                error_code="slack_timeout",
                error_summary="Timed out.",
            )
        )
        second_delivery = repository.upsert_delivery(
            RecordAlertDeliveryCommand(
                alert_event_id=created.event.id,
                channel="slack",
                status="delivered",
                attempted_at=NOW + timedelta(minutes=5),
            )
        )
        candidates = repository.list_delivery_candidates(limit=10)

        assert created.created is True
        assert duplicate.created is False
        assert duplicate.event.id == created.event.id
        assert first_delivery.attempt_count == 1
        assert second_delivery.id == first_delivery.id
        assert second_delivery.attempt_count == 2
        assert second_delivery.delivered_at == (NOW + timedelta(minutes=5)).replace(tzinfo=None)
        assert second_delivery.error_code is None
        assert len(candidates) == 1
        assert candidates[0].rule.id == rule.id
        assert candidates[0].event.id == created.event.id
        assert candidates[0].deliveries_by_channel["slack"].status == "delivered"


def test_appraisal_report_repository_loads_inputs_and_scoped_report_reads() -> None:
    with _sqlite_session() as session:
        organization, user = _create_org_member(session)
        domain = _create_domain(session, "atlasai.com")
        fact = VerifiedFact(
            domain_id=domain.id,
            auction_id=None,
            fact_type="whois",
            fact_key="registrar",
            fact_value_json={"registrar": "Example Registrar"},
            source_system="rdap",
            observed_at=NOW,
        )
        signal = DerivedSignal(
            domain_id=domain.id,
            auction_id=None,
            signal_type="valuation",
            signal_key="investment_score",
            signal_value_json={"score": "0.72"},
            input_fact_ids=[],
            input_signal_ids=[],
            algorithm_version="signals-v1",
            confidence_score=Decimal("0.8000"),
            generated_at=NOW,
        )
        session.add_all([fact, signal])
        session.flush()
        classification = ClassificationResult(
            domain_id=domain.id,
            domain_type=DomainType.BRANDABLE,
            business_category="Tech",
            language_code="en",
            tokens_json=["atlas", "ai"],
            risk_flags_json=[],
            confidence_score=Decimal("0.8700"),
            algorithm_version="classifier-v1",
            input_fact_ids=[fact.id],
            input_signal_ids=[signal.id],
        )
        session.add(classification)
        session.flush()
        valuation = ValuationRun(
            domain_id=domain.id,
            auction_id=None,
            classification_result_id=classification.id,
            status=ValuationStatus.VALUED,
            estimated_value_min=Decimal("2000.00"),
            estimated_value_max=Decimal("3500.00"),
            estimated_value_point=Decimal("2750.00"),
            currency="USD",
            value_tier=ValueTier.MEANINGFUL,
            confidence_level=ConfidenceLevel.MEDIUM,
            algorithm_version="valuation-v1",
            input_fact_ids=[],
            input_signal_ids=[signal.id],
            created_at=NOW,
        )
        session.add(valuation)
        session.flush()
        session.add_all(
            [
                ValuationReasonCode(
                    valuation_run_id=valuation.id,
                    code="strong_tld",
                    label="Strong TLD",
                    direction="positive",
                    impact_amount=Decimal("250.00"),
                    impact_weight=Decimal("0.2500"),
                    evidence_refs_json=[],
                    explanation="The .com TLD supports liquidity.",
                ),
                AIExplanation(
                    subject_type="valuation_run",
                    subject_id=valuation.id,
                    explanation_type="appraisal_summary",
                    model_name="unit-model",
                    prompt_version="report-v1",
                    input_refs_json=[],
                    structured_output_json={},
                    text="Validated explanation.",
                    validation_status="validated",
                    created_at=NOW,
                ),
                AIExplanation(
                    subject_type="valuation_run",
                    subject_id=valuation.id,
                    explanation_type="appraisal_summary",
                    model_name="unit-model",
                    prompt_version="report-v1",
                    input_refs_json=[],
                    structured_output_json={},
                    text="Pending explanation.",
                    validation_status="pending",
                    created_at=NOW,
                ),
            ]
        )
        session.commit()

        repository = AppraisalReportRepository(session)
        loaded = repository.load_report_input(
            GenerateAppraisalReportCommand(
                organization_id=organization.id,
                domain_id=domain.id,
                valuation_run_id=valuation.id,
                include_ai_explanations=True,
                report_template_version="appraisal-v1",
                created_by_user_id=user.id,
            )
        )

        assert loaded is not None
        assert loaded.domain.fqdn == "atlasai.com"
        assert loaded.classification is not None
        assert loaded.classification.domain_type == "brandable"
        assert loaded.valuation.reason_codes[0].code == "strong_tld"
        assert [fact_input.fact_key for fact_input in loaded.facts] == ["registrar"]
        assert [signal_input.signal_key for signal_input in loaded.signals] == ["investment_score"]
        assert [explanation.text for explanation in loaded.validated_ai_explanations] == [
            "Validated explanation."
        ]

        report = repository.create_report(
            organization_id=organization.id,
            domain_id=domain.id,
            valuation_run_id=valuation.id,
            status="generated",
            report_template_version="appraisal-v1",
            report_json=_report_payload(),
            generated_at=NOW,
            created_by_user_id=user.id,
        )
        scoped = repository.get_report(report.id, organization.id)
        out_of_scope = repository.get_report(report.id, uuid4())

        assert report.report_json.domain_header.fqdn == "atlasai.com"
        assert scoped is not None
        assert scoped.report_json.final_verdict.status == "valued"
        assert out_of_scope is None


def test_opportunity_repository_reads_latest_valuation_and_wholesale_signals() -> None:
    with _sqlite_session() as session:
        marketplace = _create_marketplace(session, "dynadot")
        other_marketplace = _create_marketplace(session, "dropcatch")
        domain = _create_domain(session, "atlasai.com")
        other_domain = _create_domain(session, "filterme.net")
        auction = _create_auction(
            session,
            marketplace,
            domain,
            source_item_id="dynadot-1",
            current_bid_amount=Decimal("300.00"),
            ends_at=NOW + timedelta(hours=2),
        )
        _create_auction(
            session,
            other_marketplace,
            other_domain,
            source_item_id="dropcatch-1",
            current_bid_amount=Decimal("150.00"),
            ends_at=NOW + timedelta(hours=1),
        )
        classification = ClassificationResult(
            domain_id=domain.id,
            domain_type=DomainType.BRANDABLE,
            business_category="Tech",
            language_code="en",
            tokens_json=["atlas", "ai"],
            risk_flags_json=[{"code": "clean"}],
            confidence_score=Decimal("0.9000"),
            algorithm_version="classifier-v1",
            input_fact_ids=[],
            input_signal_ids=[],
        )
        session.add(classification)
        session.flush()
        session.add_all(
            [
                _valuation_run(
                    domain,
                    classification,
                    estimated_min=Decimal("500.00"),
                    estimated_max=Decimal("750.00"),
                    created_at=NOW - timedelta(days=1),
                ),
                _valuation_run(
                    domain,
                    classification,
                    estimated_min=Decimal("2000.00"),
                    estimated_max=Decimal("4000.00"),
                    created_at=NOW,
                ),
                _derived_signal(domain, "estimated_wholesale_min", {"amount": "650"}, NOW - timedelta(days=1)),
                _derived_signal(domain, "estimated_wholesale_min", {"amount": "800"}, NOW),
                _derived_signal(domain, "estimated_wholesale_max", {"amount": "1500"}, NOW),
                _derived_signal(domain, "risk_score", {"score": "0.18"}, NOW),
            ]
        )
        session.commit()

        repository = OpportunityRepository(session)
        candidates, total = repository.list_candidates(
            UndervaluationQuery(source="dynadot", tld=".com", limit=10, offset=0)
        )

        assert total == 1
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.auction_id == auction.id
        assert candidate.fqdn == "atlasai.com"
        assert candidate.marketplace_code == "dynadot"
        assert candidate.valuation_status == "valued"
        assert candidate.confidence_level == "medium"
        assert candidate.estimated_retail_range is not None
        assert candidate.estimated_retail_range.low == "2000.00"
        assert candidate.estimated_retail_range.high == "4000.00"
        assert candidate.estimated_wholesale_range is not None
        assert candidate.estimated_wholesale_range.low == "800.00"
        assert candidate.estimated_wholesale_range.high == "1500.00"
        assert candidate.risk_score == Decimal("0.18")
        assert candidate.risk_flags == [{"code": "clean"}]


@contextmanager
def _sqlite_session() -> Iterator[Session]:
    original_types = _adapt_postgres_types_for_sqlite()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
        for column, original_type in original_types:
            column.type = original_type


def _adapt_postgres_types_for_sqlite() -> list[tuple[object, object]]:
    original_types = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            replacement = None
            if isinstance(column.type, JSONB):
                replacement = JSON()
            elif isinstance(column.type, ARRAY):
                replacement = SqliteUUIDArray()
            elif isinstance(column.type, CITEXT):
                replacement = Text()
            if replacement is not None:
                original_types.append((column, column.type))
                column.type = replacement
    return original_types


def _create_org_member(session: Session) -> tuple[Organization, User]:
    organization = Organization(
        name="Acme Domains",
        slug=f"acme-{uuid4().hex}",
        plan_code="test",
    )
    user = _user_model("analyst")
    session.add_all([organization, user])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    session.flush()
    return organization, user


def _create_user(session: Session, prefix: str) -> User:
    user = _user_model(prefix)
    session.add(user)
    session.flush()
    return user


def _user_model(prefix: str) -> User:
    return User(
        email=f"{prefix}-{uuid4().hex}@example.test",
        display_name=prefix.title(),
    )


def _create_watchlist_model(session: Session, organization: Organization, owner: User) -> Watchlist:
    watchlist = Watchlist(
        organization_id=organization.id,
        owner_user_id=owner.id,
        name="Deals",
        visibility="private",
    )
    session.add(watchlist)
    session.flush()
    return watchlist


def _create_domain(session: Session, fqdn: str) -> Domain:
    sld, tld = fqdn.split(".", 1)
    domain = Domain(
        fqdn=fqdn,
        sld=sld,
        tld=tld,
        punycode_fqdn=fqdn,
        unicode_fqdn=fqdn,
        is_valid=True,
    )
    session.add(domain)
    session.flush()
    return domain


def _create_marketplace(session: Session, code: str) -> SourceMarketplace:
    marketplace = SourceMarketplace(
        code=code,
        display_name=code.title(),
        base_url=f"https://{code}.example.test",
        terms_review_status="approved",
        is_enabled=True,
    )
    session.add(marketplace)
    session.flush()
    return marketplace


def _create_auction(
    session: Session,
    marketplace: SourceMarketplace,
    domain: Domain,
    *,
    source_item_id: str = "auction-1",
    status: AuctionStatus = AuctionStatus.OPEN,
    current_bid_amount: Decimal = Decimal("250.00"),
    ends_at: datetime = NOW + timedelta(days=1),
) -> Auction:
    auction = Auction(
        marketplace_id=marketplace.id,
        domain_id=domain.id,
        source_item_id=source_item_id,
        source_url=f"https://{marketplace.code}.example.test/{source_item_id}",
        auction_type=AuctionType.EXPIRED,
        status=status,
        starts_at=NOW - timedelta(days=1),
        ends_at=ends_at,
        currency="USD",
        current_bid_amount=current_bid_amount,
        min_bid_amount=Decimal("10.00"),
        bid_count=3,
        watchers_count=8,
        normalized_payload_json={"source_item_id": source_item_id},
        first_seen_at=NOW - timedelta(days=1),
        last_seen_at=NOW,
    )
    session.add(auction)
    session.flush()
    return auction


def _valuation_run(
    domain: Domain,
    classification: ClassificationResult,
    *,
    estimated_min: Decimal,
    estimated_max: Decimal,
    created_at: datetime,
) -> ValuationRun:
    return ValuationRun(
        domain_id=domain.id,
        auction_id=None,
        classification_result_id=classification.id,
        status=ValuationStatus.VALUED,
        estimated_value_min=estimated_min,
        estimated_value_max=estimated_max,
        estimated_value_point=(estimated_min + estimated_max) / Decimal("2"),
        currency="USD",
        value_tier=ValueTier.MEANINGFUL,
        confidence_level=ConfidenceLevel.MEDIUM,
        algorithm_version="valuation-v1",
        input_fact_ids=[],
        input_signal_ids=[],
        created_at=created_at,
    )


def _derived_signal(
    domain: Domain,
    signal_key: str,
    signal_value_json: dict[str, object],
    generated_at: datetime,
) -> DerivedSignal:
    return DerivedSignal(
        domain_id=domain.id,
        auction_id=None,
        signal_type="valuation",
        signal_key=signal_key,
        signal_value_json=signal_value_json,
        input_fact_ids=[],
        input_signal_ids=[],
        algorithm_version="signals-v1",
        confidence_score=Decimal("0.8000"),
        generated_at=generated_at,
    )


def _report_payload() -> dict[str, object]:
    return {
        "schema_version": "appraisal-report-v1",
        "report_template_version": "appraisal-v1",
        "generated_at": NOW.isoformat(),
        "valuation_status": "valued",
        "domain_header": {
            "fqdn": "atlasai.com",
            "sld": "atlasai",
            "tld": "com",
            "punycode_fqdn": "atlasai.com",
            "unicode_fqdn": "atlasai.com",
            "is_valid": True,
        },
        "classification": {
            "domain_type": "brandable",
            "business_category": "Tech",
            "language_code": "en",
            "confidence_score": 0.87,
            "risk_flags": [],
        },
        "recommended_listing_price": {"amount": "2750.00", "currency": "USD"},
        "fair_market_range": {"low": "2000.00", "high": "3500.00", "currency": "USD"},
        "confidence_level": "medium",
        "whois_intelligence": {"status": "available", "registrar": "Example Registrar"},
        "tld_ecosystem_summary": {"status": "unknown"},
        "market_analysis_summary": {},
        "score_breakdown": {"overall_investment_score": 0.72},
        "risks": [],
        "final_verdict": {
            "status": "valued",
            "headline": "Valued domain",
            "summary": "AtlasAI.com has a supported valuation.",
            "value_tier": "meaningful",
            "pricing_posture": "bin",
            "action": "list",
        },
        "pricing_guidance": {
            "pricing_strategy": "bin",
            "estimated_retail_range": {"low": "2000.00", "high": "3500.00", "currency": "USD"},
            "listing_confidence": "medium",
            "notes": [],
        },
        "supporting_facts": [],
        "derived_signals": [],
        "validated_ai_explanations": [],
    }
