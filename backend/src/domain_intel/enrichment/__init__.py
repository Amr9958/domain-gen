"""Enrichment contracts and provider adapters."""

from domain_intel.enrichment.contracts import (
    DomainTarget,
    EnrichmentError,
    EnrichmentRequest,
    EnrichmentResult,
    ProviderExecutionResult,
    ProviderOutcome,
    RetryPolicy,
    UnresolvedObservation,
    VerifiedFactDraft,
    WebsiteCheckDraft,
)
from domain_intel.enrichment.freshness import EnrichmentFreshnessPolicy
from domain_intel.enrichment.providers import (
    HttpWebsiteInspectionProvider,
    StaticDnsProvider,
    StaticDnsRecordSet,
    StaticWhoisRdapProvider,
    StaticWhoisRdapRecord,
    UnavailableDnsProvider,
    UnavailableWhoisRdapProvider,
)

__all__ = [
    "DomainTarget",
    "EnrichmentError",
    "EnrichmentFreshnessPolicy",
    "EnrichmentRequest",
    "EnrichmentResult",
    "HttpWebsiteInspectionProvider",
    "ProviderExecutionResult",
    "ProviderOutcome",
    "RetryPolicy",
    "StaticDnsProvider",
    "StaticDnsRecordSet",
    "StaticWhoisRdapProvider",
    "StaticWhoisRdapRecord",
    "UnavailableDnsProvider",
    "UnavailableWhoisRdapProvider",
    "UnresolvedObservation",
    "VerifiedFactDraft",
    "WebsiteCheckDraft",
]
