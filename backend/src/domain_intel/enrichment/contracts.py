"""Typed contracts for domain enrichment providers and orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Sequence
from uuid import UUID

from domain_intel.core.enums import (
    EnrichmentCheckType,
    EnrichmentStatus,
)


@dataclass(frozen=True)
class RetryPolicy:
    """Retry-friendly provider settings without hard-wiring network behavior."""

    max_attempts: int = 3
    retryable_status_codes: Sequence[int] = (408, 425, 429, 500, 502, 503, 504)


@dataclass(frozen=True)
class DomainTarget:
    """Minimal domain identity required by enrichment providers."""

    domain_id: UUID
    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: Optional[str] = None
    unicode_fqdn: Optional[str] = None


@dataclass(frozen=True)
class VerifiedFactDraft:
    """Write-ready verified fact payload before persistence."""

    fact_type: str
    fact_key: str
    fact_value_json: Dict[str, Any]
    source_system: str
    observed_at: datetime
    source_url: Optional[str] = None
    evidence_ref: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    provider_version: Optional[str] = None
    parser_version: Optional[str] = None


@dataclass(frozen=True)
class WebsiteCheckDraft:
    """Write-ready website check row before persistence."""

    checked_at: datetime
    start_url: str
    final_url: Optional[str]
    http_status: Optional[int]
    redirect_count: int
    tls_valid: Optional[bool]
    title: Optional[str]
    content_hash: Optional[str]
    technology_json: Dict[str, Any] = field(default_factory=dict)
    created_fact_ids: List[UUID] = field(default_factory=list)


@dataclass(frozen=True)
class EnrichmentError:
    """Structured, retry-aware enrichment error."""

    code: str
    message: str
    retryable: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnresolvedObservation:
    """Explicitly unresolved or unknown output from a provider."""

    scope: str
    key: str
    reason: str
    retryable: bool


@dataclass(frozen=True)
class ProviderExecutionResult:
    """Provider result separated into facts, website checks, and unresolved outputs."""

    provider_name: str
    status: EnrichmentStatus
    verified_facts: List[VerifiedFactDraft] = field(default_factory=list)
    unresolved: List[UnresolvedObservation] = field(default_factory=list)
    website_check: Optional[WebsiteCheckDraft] = None
    errors: List[EnrichmentError] = field(default_factory=list)
    cache_hit: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderOutcome:
    """Persisted outcome summary for one enrichment check."""

    check: EnrichmentCheckType
    provider_name: str
    status: EnrichmentStatus
    created_fact_ids: List[UUID] = field(default_factory=list)
    cache_hit: bool = False
    unresolved: List[UnresolvedObservation] = field(default_factory=list)
    errors: List[EnrichmentError] = field(default_factory=list)


@dataclass(frozen=True)
class EnrichmentRequest:
    """Service request aligned to the shared enrichment contract."""

    domain_id: UUID
    fqdn: Optional[str] = None
    checks: List[EnrichmentCheckType] = field(
        default_factory=lambda: [
            EnrichmentCheckType.RDAP,
            EnrichmentCheckType.DNS,
            EnrichmentCheckType.WEBSITE,
        ]
    )
    force_refresh: bool = False
    correlation_id: Optional[UUID] = None


@dataclass(frozen=True)
class EnrichmentResult:
    """Service response for a full enrichment attempt."""

    enrichment_run_id: UUID
    status: EnrichmentStatus
    created_fact_ids: List[UUID] = field(default_factory=list)
    website_check_id: Optional[UUID] = None
    provider_outcomes: List[ProviderOutcome] = field(default_factory=list)
    errors: List[EnrichmentError] = field(default_factory=list)


class WhoisRdapProvider(Protocol):
    """Provider abstraction for WHOIS or RDAP-backed registration facts."""

    provider_name: str

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        """Fetch registration facts for a domain target."""


class DnsMxProvider(Protocol):
    """Provider abstraction for DNS and MX lookups."""

    provider_name: str

    def lookup(self, target: DomainTarget) -> ProviderExecutionResult:
        """Fetch DNS facts for a domain target."""


class WebsiteInspectionProvider(Protocol):
    """Provider abstraction for website and landing-page inspection."""

    provider_name: str

    def inspect(self, target: DomainTarget) -> ProviderExecutionResult:
        """Inspect the domain website and classify the resulting page."""
