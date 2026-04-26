"""Freshness windows for enrichment caching and refresh decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from domain_intel.core.enums import EnrichmentCheckType


@dataclass(frozen=True)
class EnrichmentFreshnessPolicy:
    """Deterministic TTLs for enrichment checks."""

    rdap_ttl: timedelta = timedelta(days=7)
    dns_ttl: timedelta = timedelta(hours=24)
    website_ttl: timedelta = timedelta(hours=12)

    def ttl_for(self, check: EnrichmentCheckType) -> timedelta:
        """Return the freshness window for a given enrichment check."""

        if check is EnrichmentCheckType.RDAP:
            return self.rdap_ttl
        if check is EnrichmentCheckType.DNS:
            return self.dns_ttl
        return self.website_ttl

    def is_fresh(
        self,
        check: EnrichmentCheckType,
        observed_at: datetime | None,
        now: datetime,
    ) -> bool:
        """Return whether existing data is fresh enough to skip a provider call."""

        if observed_at is None:
            return False
        return observed_at + self.ttl_for(check) >= now
