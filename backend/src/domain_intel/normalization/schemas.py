"""Typed contracts for raw-auction normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from domain_intel.core.enums import AuctionStatus, AuctionType, MarketplaceCode
from domain_intel.marketplaces.schemas import ModuleError, Money, enum_value, json_compatible, utc_isoformat


@dataclass(frozen=True)
class NormalizeRawItemRequest:
    """Input required to transform one stored raw observation into canonical records."""

    raw_auction_item_id: str
    marketplace_code: MarketplaceCode | str
    source_item_id: str
    raw_payload_json: Mapping[str, Any]
    source_url: str | None
    captured_at: datetime


@dataclass(frozen=True)
class DomainIdentity:
    """Canonical domain identity extracted from source evidence."""

    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: str | None
    is_valid: bool

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "fqdn": self.fqdn,
            "sld": self.sld,
            "tld": self.tld,
            "punycode_fqdn": self.punycode_fqdn,
            "unicode_fqdn": self.unicode_fqdn,
            "is_valid": self.is_valid,
        }


@dataclass(frozen=True)
class CanonicalAuction:
    """Canonical auction state derived from one raw source observation."""

    marketplace_code: MarketplaceCode | str
    source_item_id: str
    source_url: str | None
    auction_type: AuctionType | str
    status: AuctionStatus | str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    current_bid: Money | None = None
    min_bid: Money | None = None
    bid_count: int | None = None
    watchers_count: int | None = None
    normalized_payload_json: Mapping[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "marketplace_code": enum_value(self.marketplace_code),
            "source_item_id": self.source_item_id,
            "source_url": self.source_url,
            "auction_type": enum_value(self.auction_type),
            "status": enum_value(self.status),
            "starts_at": utc_isoformat(self.starts_at) if self.starts_at else None,
            "ends_at": utc_isoformat(self.ends_at) if self.ends_at else None,
            "current_bid": self.current_bid.to_api_dict() if self.current_bid else None,
            "min_bid": self.min_bid.to_api_dict() if self.min_bid else None,
            "bid_count": self.bid_count,
            "watchers_count": self.watchers_count,
            "normalized_payload_json": json_compatible(self.normalized_payload_json),
        }


@dataclass(frozen=True)
class AuctionSnapshot:
    """Historical snapshot derived from one raw observation."""

    captured_at: datetime
    status: AuctionStatus | str
    current_bid: Money | None = None
    bid_count: int | None = None
    watchers_count: int | None = None

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "captured_at": utc_isoformat(self.captured_at),
            "status": enum_value(self.status),
            "current_bid": self.current_bid.to_api_dict() if self.current_bid else None,
            "bid_count": self.bid_count,
            "watchers_count": self.watchers_count,
        }


@dataclass(frozen=True)
class EvidenceRef:
    """Reference back to raw evidence used for normalization."""

    type: str
    id: str
    source: str
    observed_at: datetime

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "source": self.source,
            "observed_at": utc_isoformat(self.observed_at),
        }


@dataclass(frozen=True)
class NormalizeRawItemResponse:
    """Normalization output bundle for one raw source observation."""

    domain: DomainIdentity | None
    auction: CanonicalAuction | None
    snapshot: AuctionSnapshot | None
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    errors: list[ModuleError] = field(default_factory=list)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.to_api_dict() if self.domain else None,
            "auction": self.auction.to_api_dict() if self.auction else None,
            "snapshot": self.snapshot.to_api_dict() if self.snapshot else None,
            "evidence_refs": [ref.to_api_dict() for ref in self.evidence_refs],
            "errors": [error.to_api_dict() for error in self.errors],
        }


class AuctionNormalizer(Protocol):
    """Stable boundary between raw marketplace observations and canonical mapping."""

    def normalize_raw_item(self, request: NormalizeRawItemRequest) -> NormalizeRawItemResponse:
        """Normalize one raw marketplace observation."""
