"""Shared marketplace adapter interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol

from domain_intel.marketplaces.schemas import FetchedPage, FetchAuctionItemsRequest, FetchAuctionItemsResponse


class PageFetchError(RuntimeError):
    """Raised when a listing page cannot be fetched safely."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "page_fetch_failed",
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class PageFetcher(Protocol):
    """Transport boundary used by source adapters."""

    def fetch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> FetchedPage:
        """Fetch a page and return decoded text."""


class MarketplaceAdapter(Protocol):
    """Stable adapter contract for marketplace ingestion workers."""

    def fetch_auction_items(self, request: FetchAuctionItemsRequest) -> FetchAuctionItemsResponse:
        """Fetch one page of source auction items."""


@dataclass(frozen=True)
class DeduplicationKey:
    """Stable hook key for external or per-run deduplication stores."""

    marketplace_code: str
    source_item_id: str
    raw_payload_hash: str

    @property
    def value(self) -> str:
        return f"{self.marketplace_code}:{self.source_item_id}:{self.raw_payload_hash}"


class DeduplicationStore(Protocol):
    """Optional store used to avoid emitting duplicate observations."""

    def seen_before(self, key: DeduplicationKey) -> bool:
        """Return True when the observation was already emitted or stored."""

    def mark_seen(self, key: DeduplicationKey, *, observed_at: datetime) -> None:
        """Persist that an observation has been emitted."""


class InMemoryDeduplicationStore:
    """Simple per-process dedup store useful for tests and single-run jobs."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def seen_before(self, key: DeduplicationKey) -> bool:
        return key.value in self._seen

    def mark_seen(self, key: DeduplicationKey, *, observed_at: datetime) -> None:
        _ = observed_at
        self._seen.add(key.value)
