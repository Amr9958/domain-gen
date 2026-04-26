"""Enrichment service orchestration tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Dict, Iterable, List
from uuid import UUID, uuid4

from domain_intel.core.enums import EnrichmentCheckType, EnrichmentStatus, StarterDomainLabel
from domain_intel.enrichment.contracts import (
    DerivedSignalDraft,
    DomainTarget,
    EnrichmentError,
    EnrichmentRequest,
    ProviderExecutionResult,
    UnresolvedObservation,
    VerifiedFactDraft,
    WebsiteCheckDraft,
)
from domain_intel.enrichment.providers import (
    StaticDnsProvider,
    StaticDnsRecordSet,
    StaticWhoisRdapProvider,
    StaticWhoisRdapRecord,
    UnavailableDnsProvider,
)
from domain_intel.services.enrichment_service import EnrichmentService


@dataclass
class FakeDomain:
    id: UUID
    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: str


@dataclass
class FakeRun:
    id: UUID
    domain_id: UUID
    run_type: str
    provider: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    error_summary: str | None = None
    created_fact_ids: List[UUID] = field(default_factory=list)


class FakeRepository:
    def __init__(self, domain: FakeDomain) -> None:
        self.domain = domain
        self.latest_fact_times: Dict[str, datetime] = {}
        self.latest_website_check_time: datetime | None = None
        self.runs: List[FakeRun] = []
        self.persisted_facts: List[VerifiedFactDraft] = []
        self.persisted_signals: List[DerivedSignalDraft] = []
        self.persisted_website_checks: List[WebsiteCheckDraft] = []
        self.commit_called = False

    def get_domain(self, domain_id: UUID) -> FakeDomain | None:
        return self.domain if domain_id == self.domain.id else None

    def latest_fact_observed_at(self, domain_id: UUID, fact_type: str) -> datetime | None:
        return self.latest_fact_times.get(fact_type)

    def latest_website_check_at(self, domain_id: UUID) -> datetime | None:
        return self.latest_website_check_time

    def create_enrichment_run(
        self,
        *,
        domain_id: UUID,
        run_type: str,
        provider: str,
        status: EnrichmentStatus,
        started_at: datetime,
    ) -> FakeRun:
        run = FakeRun(
            id=uuid4(),
            domain_id=domain_id,
            run_type=run_type,
            provider=provider,
            status=status.value,
            started_at=started_at,
        )
        self.runs.append(run)
        return run

    def update_enrichment_run(
        self,
        run: FakeRun,
        *,
        status: EnrichmentStatus,
        completed_at: datetime | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
        created_fact_ids: Iterable[UUID] | None = None,
    ) -> None:
        run.status = status.value
        run.completed_at = completed_at
        run.error_code = error_code
        run.error_summary = error_summary
        if created_fact_ids is not None:
            run.created_fact_ids = list(created_fact_ids)

    def create_verified_facts(self, domain_id: UUID, drafts: Iterable[VerifiedFactDraft]) -> List[SimpleNamespace]:
        rows: List[SimpleNamespace] = []
        for draft in drafts:
            fact_id = uuid4()
            self.persisted_facts.append(draft)
            rows.append(SimpleNamespace(id=fact_id))
        return rows

    def create_derived_signals(self, domain_id: UUID, drafts: Iterable[DerivedSignalDraft]) -> List[SimpleNamespace]:
        rows: List[SimpleNamespace] = []
        for draft in drafts:
            signal_id = uuid4()
            self.persisted_signals.append(draft)
            rows.append(SimpleNamespace(id=signal_id))
        return rows

    def create_website_check(self, domain_id: UUID, draft: WebsiteCheckDraft) -> SimpleNamespace:
        self.persisted_website_checks.append(draft)
        self.latest_website_check_time = draft.checked_at
        return SimpleNamespace(id=uuid4())

    def commit(self) -> None:
        self.commit_called = True


class FakeWebsiteProvider:
    provider_name = "fake_website"

    def __init__(self, status: str = "active_website") -> None:
        self.status = status
        self.called = False

    def inspect(self, target: DomainTarget) -> ProviderExecutionResult:
        self.called = True
        observed_at = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=EnrichmentStatus.COMPLETED,
            verified_facts=[
                VerifiedFactDraft(
                    fact_type="website",
                    fact_key="http_observation",
                    fact_value_json={"http_status": 200, "final_url": f"https://{target.fqdn}"},
                    source_system=self.provider_name,
                    observed_at=observed_at,
                )
            ],
            derived_signals=[
                DerivedSignalDraft(
                    signal_type="website_classification",
                    signal_key="page_category",
                    signal_value_json={"category": self.status, "is_for_sale": False},
                    algorithm_version="website-classifier-v1",
                    generated_at=observed_at,
                )
            ],
            website_check=WebsiteCheckDraft(
                checked_at=observed_at,
                start_url=f"https://{target.fqdn}",
                final_url=f"https://{target.fqdn}",
                http_status=200,
                redirect_count=0,
                tls_valid=True,
                title="Live Site",
                content_hash="hash",
                technology_json={"server": "test"},
            ),
        )


class RecordingDnsProvider:
    provider_name = "recording_dns"

    def __init__(self) -> None:
        self.called = False

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        self.called = True
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=EnrichmentStatus.COMPLETED,
        )


def _domain(fqdn: str, sld: str) -> FakeDomain:
    domain_id = uuid4()
    return FakeDomain(
        id=domain_id,
        fqdn=fqdn,
        sld=sld,
        tld="com",
        punycode_fqdn=fqdn,
        unicode_fqdn=fqdn,
    )


def test_enrichment_service_persists_facts_signals_and_website_checks() -> None:
    domain = _domain("miamiplumber.com", "miamiplumber")
    repository = FakeRepository(domain)
    observed_at = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    service = EnrichmentService(
        repository=repository,
        whois_rdap_provider=StaticWhoisRdapProvider(
            {
                domain.fqdn: StaticWhoisRdapRecord(
                    observed_at=observed_at,
                    registrar_name="Example Registrar",
                    registration_statuses=["active"],
                )
            }
        ),
        dns_provider=StaticDnsProvider(
            {
                domain.fqdn: StaticDnsRecordSet(
                    observed_at=observed_at,
                    a_records=["203.0.113.10"],
                    mx_records=[{"host": "mail.example.test", "priority": 10}],
                )
            }
        ),
        website_provider=FakeWebsiteProvider(),
    )

    result = service.enrich_domain(EnrichmentRequest(domain_id=domain.id))

    assert result.status == EnrichmentStatus.COMPLETED
    assert result.website_check_id is not None
    assert result.created_fact_ids
    assert result.created_signal_ids
    assert repository.commit_called is True
    assert repository.runs[-1].status == EnrichmentStatus.COMPLETED.value
    assert result.classification_hint is not None
    assert result.classification_hint.primary_label == StarterDomainLabel.GEO_SERVICE


def test_enrichment_service_marks_partial_when_a_provider_fails() -> None:
    domain = _domain("vectorai.com", "vectorai")
    repository = FakeRepository(domain)
    observed_at = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    service = EnrichmentService(
        repository=repository,
        whois_rdap_provider=StaticWhoisRdapProvider(
            {
                domain.fqdn: StaticWhoisRdapRecord(
                    observed_at=observed_at,
                    registrar_name="Example Registrar",
                )
            }
        ),
        dns_provider=UnavailableDnsProvider(),
        website_provider=FakeWebsiteProvider(),
    )

    result = service.enrich_domain(EnrichmentRequest(domain_id=domain.id))

    assert result.status == EnrichmentStatus.PARTIAL
    assert result.errors[0].code == "dns_provider_unavailable"
    assert repository.runs[-1].error_code == "dns_provider_unavailable"


def test_enrichment_service_uses_freshness_cache_before_calling_provider() -> None:
    domain = _domain("atlas.com", "atlas")
    repository = FakeRepository(domain)
    repository.latest_fact_times["dns"] = datetime.now(timezone.utc) - timedelta(hours=1)
    dns_provider = RecordingDnsProvider()
    service = EnrichmentService(
        repository=repository,
        whois_rdap_provider=StaticWhoisRdapProvider({}),
        dns_provider=dns_provider,
        website_provider=FakeWebsiteProvider(),
    )

    result = service.enrich_domain(
        EnrichmentRequest(
            domain_id=domain.id,
            checks=[EnrichmentCheckType.DNS],
            force_refresh=False,
        )
    )

    assert result.status == EnrichmentStatus.COMPLETED
    assert dns_provider.called is False
    assert result.provider_outcomes[0].cache_hit is True
    assert repository.runs[-1].status == EnrichmentStatus.COMPLETED.value
