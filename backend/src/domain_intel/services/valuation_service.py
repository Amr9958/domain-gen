"""Thin service wrapper for valuation provider lookup and deterministic scoring."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from domain_intel.core.enums import ValuationRefusalCode
from domain_intel.valuation.engine import RuleBasedValuationEngine
from domain_intel.valuation.interfaces import (
    ComparableSalesProvider,
    ComparableSalesQuery,
    EcosystemSignalProvider,
    EcosystemSignalQuery,
    NullComparableSalesProvider,
    NullEcosystemSignalProvider,
    ValuationProviderError,
)
from domain_intel.valuation.models import DomainValuationRequest, ValuationResult


class ValuationService:
    """Application service for classification-aware valuation."""

    def __init__(
        self,
        comparable_sales_provider: Optional[ComparableSalesProvider] = None,
        ecosystem_signal_provider: Optional[EcosystemSignalProvider] = None,
        engine: Optional[RuleBasedValuationEngine] = None,
    ) -> None:
        self.comparable_sales_provider = comparable_sales_provider or NullComparableSalesProvider()
        self.ecosystem_signal_provider = ecosystem_signal_provider or NullEcosystemSignalProvider()
        self.engine = engine or RuleBasedValuationEngine()

    def value_domain(self, request: DomainValuationRequest) -> ValuationResult:
        """Resolve provider inputs and return a deterministic valuation result."""

        if request.classification is None:
            return self.engine.value_domain(request)

        try:
            comparable_support = request.comparable_support or self.comparable_sales_provider.lookup_support(
                ComparableSalesQuery(
                    domain=request.domain,
                    classification=request.classification,
                    currency=request.currency,
                )
            )
            ecosystem_signals = request.ecosystem_signals or self.ecosystem_signal_provider.lookup_signals(
                EcosystemSignalQuery(
                    domain=request.domain,
                    classification=request.classification,
                )
            )
        except ValuationProviderError as exc:
            return self.engine.build_refusal_result(
                request,
                ValuationRefusalCode.PROVIDER_FAILURE,
                f"Supporting provider lookup failed: {exc}",
                ("Retry the provider lookup or supply manual support inputs.",),
            )

        resolved_request = replace(
            request,
            comparable_support=comparable_support,
            ecosystem_signals=ecosystem_signals,
        )
        return self.engine.value_domain(resolved_request)
