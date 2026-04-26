"""Domain enrichment orchestration service."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List
from uuid import UUID

from domain_intel.core.enums import EnrichmentCheckType, EnrichmentStatus
from domain_intel.db.base import utc_now
from domain_intel.enrichment.contracts import (
    DnsMxProvider,
    DomainTarget,
    EnrichmentError,
    EnrichmentRequest,
    EnrichmentResult,
    ProviderExecutionResult,
    ProviderOutcome,
    WebsiteCheckDraft,
    WebsiteInspectionProvider,
    WhoisRdapProvider,
)
from domain_intel.enrichment.freshness import EnrichmentFreshnessPolicy
from domain_intel.repositories.enrichment_repository import EnrichmentRepository


class EnrichmentService:
    """Evidence-first enrichment orchestration for WHOIS/RDAP, DNS, and websites."""

    def __init__(
        self,
        repository: EnrichmentRepository,
        whois_rdap_provider: WhoisRdapProvider,
        dns_provider: DnsMxProvider,
        website_provider: WebsiteInspectionProvider,
        freshness_policy: EnrichmentFreshnessPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.whois_rdap_provider = whois_rdap_provider
        self.dns_provider = dns_provider
        self.website_provider = website_provider
        self.freshness_policy = freshness_policy or EnrichmentFreshnessPolicy()

    def enrich_domain(self, request: EnrichmentRequest) -> EnrichmentResult:
        """Run deterministic enrichment steps and persist facts and website checks."""

        started_at = utc_now()
        target = self._load_target(request.domain_id, request.fqdn)
        checks = self._normalized_checks(request.checks)
        run = self.repository.create_enrichment_run(
            domain_id=target.domain_id,
            run_type=self._run_type_label(checks),
            provider=self._provider_label(checks),
            status=EnrichmentStatus.PENDING,
            started_at=started_at,
        )
        self.repository.update_enrichment_run(run, status=EnrichmentStatus.IN_PROGRESS)

        created_fact_ids: List[UUID] = []
        provider_outcomes: List[ProviderOutcome] = []
        website_check_id: UUID | None = None
        errors: List[EnrichmentError] = []

        for check in checks:
            result = self._run_provider(check=check, target=target, force_refresh=request.force_refresh, now=started_at)
            outcome, persisted_website_check_id = self._persist_provider_result(
                target=target,
                check=check,
                result=result,
            )
            provider_outcomes.append(outcome)
            created_fact_ids.extend(outcome.created_fact_ids)
            errors.extend(outcome.errors)
            if persisted_website_check_id is not None:
                website_check_id = persisted_website_check_id

        final_status = self._final_status(provider_outcomes)
        error_code, error_summary = self._error_summary(errors)
        self.repository.update_enrichment_run(
            run,
            status=final_status,
            completed_at=utc_now(),
            error_code=error_code,
            error_summary=error_summary,
            created_fact_ids=created_fact_ids,
        )
        self.repository.commit()
        return EnrichmentResult(
            enrichment_run_id=run.id,
            status=final_status,
            created_fact_ids=created_fact_ids,
            website_check_id=website_check_id,
            provider_outcomes=provider_outcomes,
            errors=errors,
        )

    def _load_target(self, domain_id: UUID, fqdn_override: str | None) -> DomainTarget:
        domain = self.repository.get_domain(domain_id)
        if domain is None:
            raise ValueError(f"Domain {domain_id} was not found.")
        return DomainTarget(
            domain_id=domain.id,
            fqdn=fqdn_override or domain.fqdn,
            sld=domain.sld,
            tld=domain.tld,
            punycode_fqdn=domain.punycode_fqdn,
            unicode_fqdn=domain.unicode_fqdn,
        )

    def _normalized_checks(self, checks: Iterable[EnrichmentCheckType]) -> List[EnrichmentCheckType]:
        normalized: List[EnrichmentCheckType] = []
        seen = set()
        for check in checks:
            normalized_check = check if isinstance(check, EnrichmentCheckType) else EnrichmentCheckType(str(check))
            if normalized_check not in seen:
                normalized.append(normalized_check)
                seen.add(normalized_check)
        if normalized:
            return normalized
        return [
            EnrichmentCheckType.RDAP,
            EnrichmentCheckType.DNS,
            EnrichmentCheckType.WEBSITE,
        ]

    def _run_provider(
        self,
        *,
        check: EnrichmentCheckType,
        target: DomainTarget,
        force_refresh: bool,
        now: datetime,
    ) -> ProviderExecutionResult:
        if not force_refresh and self._is_fresh(check, target.domain_id, now):
            provider_name = self._provider_name_for(check)
            return ProviderExecutionResult(
                provider_name=provider_name,
                status=EnrichmentStatus.COMPLETED,
                cache_hit=True,
                metadata={"cache_strategy": "freshness_window_skip"},
            )

        if check is EnrichmentCheckType.RDAP:
            return self.whois_rdap_provider.lookup(target)
        if check is EnrichmentCheckType.DNS:
            return self.dns_provider.lookup(target)
        return self.website_provider.inspect(target)

    def _persist_provider_result(
        self,
        *,
        target: DomainTarget,
        check: EnrichmentCheckType,
        result: ProviderExecutionResult,
    ) -> tuple[ProviderOutcome, UUID | None]:
        created_fact_ids: List[UUID] = []
        website_check_id: UUID | None = None

        if result.verified_facts:
            fact_rows = self.repository.create_verified_facts(target.domain_id, result.verified_facts)
            created_fact_ids.extend(row.id for row in fact_rows)

        if result.website_check is not None:
            website_check = self.repository.create_website_check(
                target.domain_id,
                draft=WebsiteCheckDraft(
                    checked_at=result.website_check.checked_at,
                    start_url=result.website_check.start_url,
                    final_url=result.website_check.final_url,
                    http_status=result.website_check.http_status,
                    redirect_count=result.website_check.redirect_count,
                    tls_valid=result.website_check.tls_valid,
                    title=result.website_check.title,
                    content_hash=result.website_check.content_hash,
                    technology_json=result.website_check.technology_json,
                    created_fact_ids=created_fact_ids,
                ),
            )
            website_check_id = website_check.id

        return (
            ProviderOutcome(
                check=check,
                provider_name=result.provider_name,
                status=result.status,
                created_fact_ids=created_fact_ids,
                cache_hit=result.cache_hit,
                unresolved=result.unresolved,
                errors=result.errors,
            ),
            website_check_id,
        )

    def _is_fresh(self, check: EnrichmentCheckType, domain_id: UUID, now: datetime) -> bool:
        if check is EnrichmentCheckType.WEBSITE:
            observed_at = self.repository.latest_website_check_at(domain_id)
        elif check is EnrichmentCheckType.RDAP:
            observed_at = self.repository.latest_fact_observed_at(domain_id, "rdap")
        else:
            observed_at = self.repository.latest_fact_observed_at(domain_id, "dns")
        return self.freshness_policy.is_fresh(check, observed_at, now)

    def _provider_name_for(self, check: EnrichmentCheckType) -> str:
        if check is EnrichmentCheckType.RDAP:
            return self.whois_rdap_provider.provider_name
        if check is EnrichmentCheckType.DNS:
            return self.dns_provider.provider_name
        return self.website_provider.provider_name

    def _run_type_label(self, checks: List[EnrichmentCheckType]) -> str:
        if len(checks) == 1:
            return checks[0].value
        return "multi_check"

    def _provider_label(self, checks: List[EnrichmentCheckType]) -> str:
        provider_names = [self._provider_name_for(check) for check in checks]
        return ",".join(provider_names)

    def _final_status(self, outcomes: List[ProviderOutcome]) -> EnrichmentStatus:
        if not outcomes:
            return EnrichmentStatus.FAILED
        if all(outcome.status is EnrichmentStatus.COMPLETED for outcome in outcomes):
            return EnrichmentStatus.COMPLETED
        if all(outcome.status is EnrichmentStatus.FAILED for outcome in outcomes):
            return EnrichmentStatus.FAILED
        return EnrichmentStatus.PARTIAL

    def _error_summary(self, errors: List[EnrichmentError]) -> tuple[str | None, str | None]:
        if not errors:
            return None, None
        return errors[0].code, "; ".join(error.message for error in errors)
