"""Provider interfaces for comparable sales and ecosystem signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain_intel.valuation.models import (
    ClassificationSnapshot,
    ComparableSalesSupport,
    DomainRecord,
    TldEcosystemSignals,
)


class ValuationProviderError(RuntimeError):
    """Raised when an external support provider fails deterministically."""


@dataclass(frozen=True)
class ComparableSalesQuery:
    """Lookup parameters for comparable-sale support."""

    domain: DomainRecord
    classification: ClassificationSnapshot
    currency: str = "USD"
    limit: int = 10


@dataclass(frozen=True)
class EcosystemSignalQuery:
    """Lookup parameters for TLD ecosystem support."""

    domain: DomainRecord
    classification: ClassificationSnapshot


class ComparableSalesProvider(Protocol):
    """Comparable-sale provider boundary."""

    def lookup_support(self, query: ComparableSalesQuery) -> ComparableSalesSupport:
        """Return verified comparable-sale support or an empty bundle."""


class EcosystemSignalProvider(Protocol):
    """TLD ecosystem provider boundary."""

    def lookup_signals(self, query: EcosystemSignalQuery) -> TldEcosystemSignals:
        """Return ecosystem signals or a placeholder bundle."""


class NullComparableSalesProvider:
    """Placeholder provider used until a live comparable source is approved."""

    def lookup_support(self, query: ComparableSalesQuery) -> ComparableSalesSupport:
        return ComparableSalesSupport()


class NullEcosystemSignalProvider:
    """Placeholder provider used until a live ecosystem source is approved."""

    def lookup_signals(self, query: EcosystemSignalQuery) -> TldEcosystemSignals:
        return TldEcosystemSignals(tld=query.domain.tld)
