"""Marketplace adapter interfaces and implementations."""

from domain_intel.marketplaces.dropcatch import DropCatchAuctionAdapter, DropCatchAuctionAdapterConfig
from domain_intel.marketplaces.base import (
    DeduplicationKey,
    DeduplicationStore,
    InMemoryDeduplicationStore,
    MarketplaceAdapter,
    PageFetchError,
    PageFetcher,
)
from domain_intel.marketplaces.schemas import (
    FetchAuctionItemsRequest,
    FetchAuctionItemsResponse,
    FetchedPage,
    ModuleError,
    Money,
    NormalizedAuctionListing,
    RawAuctionItemObservation,
)

__all__ = [
    "DeduplicationKey",
    "DeduplicationStore",
    "DropCatchAuctionAdapter",
    "DropCatchAuctionAdapterConfig",
    "FetchAuctionItemsRequest",
    "FetchAuctionItemsResponse",
    "FetchedPage",
    "InMemoryDeduplicationStore",
    "MarketplaceAdapter",
    "ModuleError",
    "Money",
    "NormalizedAuctionListing",
    "PageFetchError",
    "PageFetcher",
    "RawAuctionItemObservation",
]
