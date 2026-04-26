"""Typed marketplace adapter schemas.

These dataclasses mirror the adapter contract in api_contracts.md without
introducing a runtime dependency on a web framework or validation library.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Union

from domain_intel.core.enums import AuctionStatus, AuctionType, MarketplaceCode


JSONValue = Union[dict[str, Any], list[Any], str, int, float, bool, None]


def utc_isoformat(value: datetime) -> str:
    """Return a UTC ISO-8601 string using the contract's trailing Z style."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def enum_value(value: Enum | str | None) -> str | None:
    """Return a plain JSON string for enums while accepting existing strings."""

    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def json_compatible(value: Any) -> JSONValue:
    """Convert typed Python values into deterministic JSON-compatible values."""

    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return utc_isoformat(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return json_compatible(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_compatible(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def stable_json_dumps(payload: Mapping[str, Any]) -> str:
    """Serialize payloads in a stable way for idempotent hashing."""

    return json.dumps(
        json_compatible(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_payload_hash(payload: Mapping[str, Any]) -> str:
    """Return a sha256 hash for a JSON payload."""

    digest = hashlib.sha256(stable_json_dumps(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class Money:
    """Money value using decimal amount strings plus ISO currency."""

    amount: Decimal
    currency: str = "USD"

    def to_api_dict(self) -> dict[str, str]:
        return {
            "amount": format(self.amount.quantize(Decimal("0.01")), "f"),
            "currency": self.currency.upper(),
        }


@dataclass(frozen=True)
class ModuleError:
    """Stable adapter error object."""

    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": json_compatible(self.details),
        }


@dataclass(frozen=True)
class FetchAuctionItemsRequest:
    """Request shape for MarketplaceAdapter.fetch_auction_items."""

    marketplace_code: MarketplaceCode | str
    ingest_run_id: str
    page_cursor: str | None = None
    limit: int = 100
    started_after: datetime | None = None


@dataclass(frozen=True)
class RawAuctionItemObservation:
    """Raw marketplace observation emitted by an adapter."""

    marketplace_code: MarketplaceCode | str
    source_item_id: str
    source_url: str | None
    captured_at: datetime
    raw_payload_json: Mapping[str, Any]
    raw_payload_hash: str
    adapter_version: str
    parser_version: str

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "marketplace_code": enum_value(self.marketplace_code),
            "source_item_id": self.source_item_id,
            "source_url": self.source_url,
            "captured_at": utc_isoformat(self.captured_at),
            "raw_payload_json": json_compatible(self.raw_payload_json),
            "raw_payload_hash": self.raw_payload_hash,
            "adapter_version": self.adapter_version,
            "parser_version": self.parser_version,
        }


@dataclass(frozen=True)
class FetchAuctionItemsResponse:
    """Adapter response shape for one or more fetched listing pages."""

    items: list[RawAuctionItemObservation]
    next_page_cursor: str | None = None
    errors: list[ModuleError] = field(default_factory=list)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_api_dict() for item in self.items],
            "next_page_cursor": self.next_page_cursor,
            "errors": [error.to_api_dict() for error in self.errors],
        }


@dataclass(frozen=True)
class NormalizedAuctionListing:
    """Source-normalized auction listing fields before database persistence."""

    source_name: str
    source_listing_id: str
    domain_name: str
    sld: str
    tld: str
    auction_type: AuctionType | str
    current_price: Money | None
    min_next_bid: Money | None
    bid_count: int | None
    close_time: datetime | None
    listing_url: str | None
    traffic: int | None
    revenue: Money | None
    renewal_price: Money | None
    age_if_available: int | None
    source_status: str | None
    raw_payload: Mapping[str, Any]
    canonical_status: AuctionStatus | str = AuctionStatus.UNKNOWN

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_listing_id": self.source_listing_id,
            "domain_name": self.domain_name,
            "sld": self.sld,
            "tld": self.tld,
            "auction_type": enum_value(self.auction_type),
            "current_price": self.current_price.to_api_dict() if self.current_price else None,
            "min_next_bid": self.min_next_bid.to_api_dict() if self.min_next_bid else None,
            "bid_count": self.bid_count,
            "close_time": utc_isoformat(self.close_time) if self.close_time else None,
            "listing_url": self.listing_url,
            "traffic": self.traffic,
            "revenue": self.revenue.to_api_dict() if self.revenue else None,
            "renewal_price": self.renewal_price.to_api_dict() if self.renewal_price else None,
            "age_if_available": self.age_if_available,
            "source_status": self.source_status,
            "canonical_status": enum_value(self.canonical_status),
            "raw_payload": json_compatible(self.raw_payload),
        }


@dataclass(frozen=True)
class FetchedPage:
    """Fetched page content passed from transport to parser."""

    url: str
    status_code: int
    text: str
    headers: Mapping[str, str] = field(default_factory=dict)
