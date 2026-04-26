"""Typed contracts for marketplace ingestion and auction normalization."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class Money:
    """Contract-compatible money value with decimal string amount."""

    amount: str
    currency: str = "USD"

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class AdapterError:
    """Stable module error returned by source adapters and normalizers."""

    code: str
    message: str
    details: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class FetchAuctionItemsRequest:
    """Request shape for MarketplaceAdapter.fetch_auction_items."""

    marketplace_code: str
    ingest_run_id: str
    page_cursor: str | None = None
    limit: int = 100
    started_after: str | None = None


@dataclass(frozen=True)
class RawAuctionItem:
    """Raw marketplace observation emitted before normalization."""

    marketplace_code: str
    source_item_id: str
    source_url: str | None
    captured_at: str
    raw_payload_json: JsonDict
    raw_payload_hash: str
    adapter_version: str
    parser_version: str

    @classmethod
    def from_payload(
        cls,
        *,
        marketplace_code: str,
        source_item_id: str,
        source_url: str | None,
        captured_at: str,
        raw_payload_json: JsonDict,
        adapter_version: str,
        parser_version: str,
    ) -> "RawAuctionItem":
        """Build a raw item with a stable payload hash for idempotent storage."""
        return cls(
            marketplace_code=marketplace_code,
            source_item_id=source_item_id,
            source_url=source_url,
            captured_at=captured_at,
            raw_payload_json=raw_payload_json,
            raw_payload_hash=build_payload_hash(raw_payload_json),
            adapter_version=adapter_version,
            parser_version=parser_version,
        )

    @property
    def dedupe_key(self) -> tuple[str, str, str]:
        """Database-compatible dedupe key: marketplace, source item, payload hash."""
        return (self.marketplace_code, self.source_item_id, self.raw_payload_hash)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class FetchAuctionItemsResponse:
    """Response shape for MarketplaceAdapter.fetch_auction_items."""

    items: list[RawAuctionItem]
    next_page_cursor: str | None = None
    errors: list[AdapterError] = field(default_factory=list)

    def dedupe_keys(self) -> list[tuple[str, str, str]]:
        return [item.dedupe_key for item in self.items]

    def to_dict(self) -> JsonDict:
        return {
            "items": [item.to_dict() for item in self.items],
            "next_page_cursor": self.next_page_cursor,
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass(frozen=True)
class NormalizeRawItemRequest:
    """Request shape for AuctionNormalizer.normalize_raw_item."""

    raw_auction_item_id: str
    marketplace_code: str
    raw_payload_json: JsonDict
    source_url: str | None
    captured_at: str


@dataclass(frozen=True)
class DomainIdentity:
    """Canonical domain identity produced by normalizers."""

    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: str
    is_valid: bool

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalAuction:
    """Canonical auction data mapped from a raw source payload."""

    marketplace_code: str
    source_item_id: str
    source_url: str | None
    auction_type: str
    status: str
    starts_at: str | None = None
    ends_at: str | None = None
    current_bid: Money | None = None
    min_bid: Money | None = None
    bid_count: int | None = None
    watchers_count: int | None = None
    normalized_payload_json: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        payload = asdict(self)
        payload["current_bid"] = self.current_bid.to_dict() if self.current_bid else None
        payload["min_bid"] = self.min_bid.to_dict() if self.min_bid else None
        return payload


@dataclass(frozen=True)
class AuctionSnapshot:
    """Canonical auction snapshot generated from one raw observation."""

    captured_at: str
    status: str
    current_bid: Money | None = None
    bid_count: int | None = None
    watchers_count: int | None = None

    def to_dict(self) -> JsonDict:
        payload = asdict(self)
        payload["current_bid"] = self.current_bid.to_dict() if self.current_bid else None
        return payload


@dataclass(frozen=True)
class EvidenceRef:
    """Evidence reference linking normalized data back to raw source evidence."""

    type: str
    id: str
    source: str
    observed_at: str

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(frozen=True)
class NormalizeRawItemResponse:
    """Response shape for AuctionNormalizer.normalize_raw_item."""

    domain: DomainIdentity | None
    auction: CanonicalAuction | None
    snapshot: AuctionSnapshot | None
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    errors: list[AdapterError] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return {
            "domain": self.domain.to_dict() if self.domain else None,
            "auction": self.auction.to_dict() if self.auction else None,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "errors": [error.to_dict() for error in self.errors],
        }


def build_payload_hash(payload: JsonDict) -> str:
    """Return a stable SHA-256 hash for raw JSON-compatible payloads."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"


def utc_iso(value: datetime) -> str:
    """Format a datetime as an ISO 8601 UTC string."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
