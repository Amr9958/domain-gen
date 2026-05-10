"""Safe Dynadot API ingestion boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain_intel.marketplaces.schemas import FetchAuctionItemsRequest, FetchAuctionItemsResponse, ModuleError


@dataclass(frozen=True)
class DynadotAuctionApiConfig:
    """Configuration for a future Dynadot API-backed auction source."""

    enabled: bool = False
    base_url: str | None = None
    credential_env_var: str = "DYNADOT_API_KEY"
    default_page_size: int = 100
    request_timeout_seconds: float = 20.0

    def safe_details(self) -> dict[str, object]:
        """Return non-secret config metadata for logs and module errors."""

        return {
            "api_enabled": self.enabled,
            "api_base_url_configured": bool(self.base_url),
            "credential_env_var": self.credential_env_var,
            "default_page_size": self.default_page_size,
            "request_timeout_seconds": self.request_timeout_seconds,
        }


class DynadotAuctionApiClient(Protocol):
    """Interface for a concrete Dynadot API client."""

    def fetch_auction_items(
        self,
        request: FetchAuctionItemsRequest,
        *,
        config: DynadotAuctionApiConfig,
    ) -> FetchAuctionItemsResponse:
        """Fetch auction observations from the Dynadot API path."""


class UnavailableDynadotAuctionApiClient:
    """Safe placeholder until a reviewed Dynadot API client is installed."""

    def fetch_auction_items(
        self,
        request: FetchAuctionItemsRequest,
        *,
        config: DynadotAuctionApiConfig,
    ) -> FetchAuctionItemsResponse:
        _ = request
        return FetchAuctionItemsResponse(
            items=[],
            errors=[
                ModuleError(
                    code="api_client_unavailable",
                    message="Dynadot API ingestion is the approved production path, but no concrete API client is configured.",
                    details=config.safe_details(),
                )
            ],
        )
