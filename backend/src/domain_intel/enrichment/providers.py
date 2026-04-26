"""Provider implementations and placeholders for enrichment checks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

from domain_intel.core.enums import EnrichmentStatus, WebsitePageCategory
from domain_intel.enrichment.contracts import (
    DomainTarget,
    EnrichmentError,
    ProviderExecutionResult,
    RetryPolicy,
    UnresolvedObservation,
    VerifiedFactDraft,
    WebsiteCheckDraft,
)


@dataclass(frozen=True)
class StaticWhoisRdapRecord:
    """Static RDAP/WHOIS payload for tests and local development."""

    observed_at: datetime
    source_url: Optional[str] = None
    registrar_name: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    registration_statuses: Optional[List[str]] = None
    nameservers: Optional[List[str]] = None
    redactions: List[str] = field(default_factory=list)
    unresolved: List[UnresolvedObservation] = field(default_factory=list)


@dataclass(frozen=True)
class StaticDnsRecordSet:
    """Static DNS payload for tests and local development."""

    observed_at: datetime
    source_url: Optional[str] = None
    a_records: Optional[List[str]] = None
    aaaa_records: Optional[List[str]] = None
    cname_records: Optional[List[str]] = None
    mx_records: Optional[List[Dict[str, object]]] = None
    ns_records: Optional[List[str]] = None
    txt_records: Optional[List[str]] = None
    unresolved: List[UnresolvedObservation] = field(default_factory=list)


class StaticWhoisRdapProvider:
    """Mockable registration-data provider that never invents WHOIS facts."""

    provider_name = "static_whois_rdap"
    provider_version = "static-rdap-v1"
    parser_version = "rdap-parser-v1"

    def __init__(self, records_by_fqdn: Dict[str, StaticWhoisRdapRecord]) -> None:
        self.records_by_fqdn = {fqdn.lower(): record for fqdn, record in records_by_fqdn.items()}

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        record = self.records_by_fqdn.get(target.fqdn.lower())
        if record is None:
            return ProviderExecutionResult(
                provider_name=self.provider_name,
                status=EnrichmentStatus.FAILED,
                errors=[
                    EnrichmentError(
                        code="rdap_record_unavailable",
                        message=f"No configured RDAP record is available for {target.fqdn}.",
                        retryable=False,
                    )
                ],
            )

        facts: List[VerifiedFactDraft] = []
        if record.registrar_name is not None:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="registrar",
                    fact_value_json={"name": record.registrar_name},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )
        if record.created_at is not None:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="registration_created_at",
                    fact_value_json={"value": record.created_at.isoformat()},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )
        if record.expires_at is not None:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="registration_expires_at",
                    fact_value_json={"value": record.expires_at.isoformat()},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )
        if record.updated_at is not None:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="registration_updated_at",
                    fact_value_json={"value": record.updated_at.isoformat()},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )
        if record.registration_statuses is not None:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="registration_statuses",
                    fact_value_json={"statuses": record.registration_statuses},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )
        if record.nameservers is not None:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="nameservers",
                    fact_value_json={"hosts": record.nameservers},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )
        if record.redactions:
            facts.append(
                _fact(
                    fact_type="rdap",
                    fact_key="redactions",
                    fact_value_json={"fields": record.redactions},
                    source_system=self.provider_name,
                    observed_at=record.observed_at,
                    source_url=record.source_url,
                    provider_version=self.provider_version,
                    parser_version=self.parser_version,
                )
            )

        if facts and not record.unresolved:
            status = EnrichmentStatus.COMPLETED
        else:
            status = EnrichmentStatus.PARTIAL
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=status,
            verified_facts=facts,
            unresolved=record.unresolved,
        )


class UnavailableWhoisRdapProvider:
    """Placeholder provider used until a reviewed RDAP/WHOIS integration is approved."""

    provider_name = "whois_rdap_unavailable"

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=EnrichmentStatus.FAILED,
            errors=[
                EnrichmentError(
                    code="rdap_provider_unavailable",
                    message=f"RDAP/WHOIS provider is not configured for {target.fqdn}.",
                    retryable=True,
                )
            ],
        )


class StaticDnsProvider:
    """Mockable DNS provider that cleanly separates empty answers from unknown answers."""

    provider_name = "static_dns"
    provider_version = "static-dns-v1"
    parser_version = "dns-parser-v1"

    def __init__(self, records_by_fqdn: Dict[str, StaticDnsRecordSet]) -> None:
        self.records_by_fqdn = {fqdn.lower(): record for fqdn, record in records_by_fqdn.items()}

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        record = self.records_by_fqdn.get(target.fqdn.lower())
        if record is None:
            return ProviderExecutionResult(
                provider_name=self.provider_name,
                status=EnrichmentStatus.FAILED,
                errors=[
                    EnrichmentError(
                        code="dns_record_unavailable",
                        message=f"No configured DNS record set is available for {target.fqdn}.",
                        retryable=False,
                    )
                ],
            )

        facts = [
            _dns_fact("a_records", record.a_records, record),
            _dns_fact("aaaa_records", record.aaaa_records, record),
            _dns_fact("cname_records", record.cname_records, record),
            _dns_fact("mx_records", record.mx_records, record),
            _dns_fact("ns_records", record.ns_records, record),
            _dns_fact("txt_records", record.txt_records, record),
        ]
        resolved_facts = [fact for fact in facts if fact is not None]
        if resolved_facts and not record.unresolved:
            status = EnrichmentStatus.COMPLETED
        else:
            status = EnrichmentStatus.PARTIAL
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=status,
            verified_facts=resolved_facts,
            unresolved=record.unresolved,
        )


class UnavailableDnsProvider:
    """Placeholder provider used until a reviewed DNS resolver is approved."""

    provider_name = "dns_unavailable"

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=EnrichmentStatus.FAILED,
            errors=[
                EnrichmentError(
                    code="dns_provider_unavailable",
                    message=f"DNS provider is not configured for {target.fqdn}.",
                    retryable=True,
                )
            ],
        )


class HttpWebsiteInspectionProvider:
    """HTTP-based website inspection with rule-based page categorization."""

    provider_name = "http_website_inspector"
    provider_version = "httpx-website-v1"
    parser_version = "website-parser-v1"

    def __init__(
        self,
        client: httpx.Client | None = None,
        retry_policy: RetryPolicy = RetryPolicy(),
        user_agent: str = "domain-intel/website-inspector",
    ) -> None:
        self.client = client or httpx.Client(follow_redirects=True, timeout=10.0)
        self.retry_policy = retry_policy
        self.user_agent = user_agent

    def inspect(self, target: DomainTarget) -> ProviderExecutionResult:
        start_url = f"https://{target.fqdn}"
        tls_valid = True
        response: httpx.Response | None = None
        response_error: Exception | None = None

        try:
            response = self._request_with_retries(start_url)
        except httpx.HTTPError as exc:
            tls_valid = False
            response_error = exc
            start_url = f"http://{target.fqdn}"
            try:
                response = self._request_with_retries(start_url)
            except httpx.HTTPError as http_exc:
                response_error = http_exc

        if response is None:
            message = str(response_error) if response_error is not None else "Unknown website inspection failure."
            return ProviderExecutionResult(
                provider_name=self.provider_name,
                status=EnrichmentStatus.FAILED,
                errors=[
                    EnrichmentError(
                        code="website_request_failed",
                        message=message,
                        retryable=True,
                    )
                ],
                unresolved=[
                    UnresolvedObservation(
                        scope="website",
                        key="http_response",
                        reason="Website request could not be completed.",
                        retryable=True,
                    )
                ],
            )

        checked_at = datetime.now(timezone.utc)
        body = response.text or ""
        title = _extract_title(body)
        technologies = _extract_technologies(response, body)
        indicator_payload = _extract_page_indicators(body)
        category, reasons = _classify_page(
            start_url=start_url,
            final_url=str(response.url),
            status_code=response.status_code,
            title=title,
            body=body,
            indicators=indicator_payload,
        )

        facts = [
            _fact(
                fact_type="website",
                fact_key="http_observation",
                fact_value_json={
                    "start_url": start_url,
                    "final_url": str(response.url),
                    "http_status": response.status_code,
                    "redirect_count": len(response.history),
                    "tls_valid": tls_valid,
                },
                source_system=self.provider_name,
                observed_at=checked_at,
                source_url=str(response.url),
                provider_version=self.provider_version,
                parser_version=self.parser_version,
            ),
            _fact(
                fact_type="website",
                fact_key="page_observation",
                fact_value_json={
                    "title": title,
                    "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "content_length": len(body),
                    "technology": technologies,
                    # Category is a provider-side interpretation kept with the observation,
                    # not a derived pricing or classification signal.
                    "page_category": category.value,
                    "page_category_reasons": reasons,
                },
                source_system=self.provider_name,
                observed_at=checked_at,
                source_url=str(response.url),
                provider_version=self.provider_version,
                parser_version=self.parser_version,
            ),
            _fact(
                fact_type="website",
                fact_key="content_indicators",
                fact_value_json=indicator_payload,
                source_system=self.provider_name,
                observed_at=checked_at,
                source_url=str(response.url),
                provider_version=self.provider_version,
                parser_version=self.parser_version,
            ),
        ]
        website_check = WebsiteCheckDraft(
            checked_at=checked_at,
            start_url=start_url,
            final_url=str(response.url),
            http_status=response.status_code,
            redirect_count=len(response.history),
            tls_valid=tls_valid,
            title=title,
            content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            technology_json=technologies,
        )
        return ProviderExecutionResult(
            provider_name=self.provider_name,
            status=EnrichmentStatus.COMPLETED,
            verified_facts=facts,
            website_check=website_check,
            metadata={
                "page_category": category.value,
                "page_category_reasons": reasons,
            },
        )

    def _request_with_retries(self, url: str) -> httpx.Response:
        last_response: httpx.Response | None = None
        last_error: httpx.HTTPError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                response = self.client.get(url, headers={"user-agent": self.user_agent})
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    raise
                continue

            last_response = response
            if response.status_code not in self.retry_policy.retryable_status_codes:
                return response
            if attempt == self.retry_policy.max_attempts:
                return response
        if last_response is None:  # pragma: no cover - defensive guard
            if last_error is not None:
                raise last_error
            raise httpx.HTTPError("No HTTP response was produced.")
        return last_response


def _dns_fact(fact_key: str, records: object, record_set: StaticDnsRecordSet) -> VerifiedFactDraft | None:
    if records is None:
        return None
    return _fact(
        fact_type="dns",
        fact_key=fact_key,
        fact_value_json={"records": records},
        source_system="static_dns",
        observed_at=record_set.observed_at,
        source_url=record_set.source_url,
        provider_version="static-dns-v1",
        parser_version="dns-parser-v1",
    )


def _fact(
    *,
    fact_type: str,
    fact_key: str,
    fact_value_json: Dict[str, object],
    source_system: str,
    observed_at: datetime,
    source_url: Optional[str],
    provider_version: str,
    parser_version: str,
) -> VerifiedFactDraft:
    return VerifiedFactDraft(
        fact_type=fact_type,
        fact_key=fact_key,
        fact_value_json=fact_value_json,
        source_system=source_system,
        observed_at=observed_at,
        source_url=source_url,
        provider_version=provider_version,
        parser_version=parser_version,
    )


def _extract_title(body: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    if match is None:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip() or None


def _extract_technologies(response: httpx.Response, body: str) -> Dict[str, object]:
    technologies: Dict[str, object] = {}
    server = response.headers.get("server")
    if server:
        technologies["server"] = server
    powered_by = response.headers.get("x-powered-by")
    if powered_by:
        technologies["powered_by"] = powered_by
    if "wp-content" in body or "wordpress" in body.lower():
        technologies["cms"] = "wordpress"
    elif "cdn.shopify.com" in body or "shopify" in body.lower():
        technologies["platform"] = "shopify"
    return technologies


def _extract_page_indicators(body: str) -> Dict[str, object]:
    text = re.sub(r"<[^>]+>", " ", body.lower())
    normalized = re.sub(r"\s+", " ", text).strip()
    parked_markers = [
        marker
        for marker in (
            "related searches",
            "sponsored listings",
            "parkingcrew",
            "bodis",
            "sedoparking",
            "this domain may be parked",
        )
        if marker in normalized
    ]
    sale_markers = [
        marker
        for marker in (
            "this domain is for sale",
            "buy this domain",
            "make an offer",
            "minimum offer",
            "bin price",
            "dan.com",
            "afternic",
            "sedo",
        )
        if marker in normalized
    ]
    return {
        "for_sale_detected": bool(sale_markers),
        "parked_detected": bool(parked_markers),
        "matched_sale_markers": sale_markers,
        "matched_parked_markers": parked_markers,
        "text_length": len(normalized),
    }


def _classify_page(
    *,
    start_url: str,
    final_url: str,
    status_code: int,
    title: str | None,
    body: str,
    indicators: Dict[str, object],
) -> tuple[WebsitePageCategory, List[str]]:
    reasons: List[str] = []
    parsed_start = urlparse(start_url)
    parsed_final = urlparse(final_url)
    start_host = parsed_start.netloc.lower().removeprefix("www.")
    final_host = parsed_final.netloc.lower().removeprefix("www.")
    if final_host and final_host != start_host:
        reasons.append(f"Final host changed from {start_host} to {final_host}.")
        return WebsitePageCategory.REDIRECT, reasons

    if indicators["for_sale_detected"]:
        reasons.append("Matched explicit domain-for-sale landing page markers.")
        return WebsitePageCategory.SALES_LANDING_PAGE, reasons

    if indicators["parked_detected"]:
        reasons.append("Matched common domain parking markers.")
        return WebsitePageCategory.PARKED_PAGE, reasons

    body_text = re.sub(r"<[^>]+>", " ", body)
    normalized_body = re.sub(r"\s+", " ", body_text).strip()
    if status_code >= 400:
        reasons.append(f"HTTP status {status_code} indicates the site is not serving a live page.")
        return WebsitePageCategory.BLANK_INACTIVE, reasons
    if len(normalized_body) < 40 and not (title and title.strip()):
        reasons.append("Body content is too small to represent a meaningful live website.")
        return WebsitePageCategory.BLANK_INACTIVE, reasons
    if title and title.lower() in {"coming soon", "under construction", "website coming soon"}:
        reasons.append(f"Title '{title}' indicates an inactive placeholder.")
        return WebsitePageCategory.BLANK_INACTIVE, reasons

    reasons.append("Page returned substantive content without parked, sale, or inactive markers.")
    return WebsitePageCategory.ACTIVE_WEBSITE, reasons
