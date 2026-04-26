"""Marketplace ingestion adapters and normalization helpers."""

from marketplaces.schemas import (
    AdapterError,
    AuctionSnapshot,
    CanonicalAuction,
    DomainIdentity,
    EvidenceRef,
    FetchAuctionItemsRequest,
    FetchAuctionItemsResponse,
    Money,
    NormalizeRawItemRequest,
    NormalizeRawItemResponse,
    RawAuctionItem,
)

__all__ = [
    "AdapterError",
    "AuctionSnapshot",
    "CanonicalAuction",
    "DomainIdentity",
    "EvidenceRef",
    "FetchAuctionItemsRequest",
    "FetchAuctionItemsResponse",
    "Money",
    "NormalizeRawItemRequest",
    "NormalizeRawItemResponse",
    "RawAuctionItem",
]
