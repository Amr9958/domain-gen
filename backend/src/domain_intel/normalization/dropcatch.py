"""DropCatch raw-observation normalization."""

from __future__ import annotations

from domain_intel.core.enums import AuctionStatus, AuctionType, MarketplaceCode
from domain_intel.marketplaces.dropcatch.parser import SOURCE_NAME, parse_dropcatch_raw_observation
from domain_intel.marketplaces.schemas import ModuleError, Money
from domain_intel.normalization.schemas import (
    AuctionSnapshot,
    CanonicalAuction,
    DomainIdentity,
    EvidenceRef,
    NormalizeRawItemRequest,
    NormalizeRawItemResponse,
)


class DropCatchAuctionNormalizer:
    """Map stored DropCatch raw observations into canonical auction payloads."""

    source_name = SOURCE_NAME

    def normalize_raw_item(self, request: NormalizeRawItemRequest) -> NormalizeRawItemResponse:
        marketplace_code = str(request.marketplace_code.value if hasattr(request.marketplace_code, "value") else request.marketplace_code)
        if marketplace_code != MarketplaceCode.DROPCATCH.value:
            return _error_response(
                ModuleError(
                    code="schema_contract_mismatch",
                    message="DropCatch normalizer only accepts marketplace_code=dropcatch.",
                    details={"marketplace_code": marketplace_code},
                )
            )

        listing = parse_dropcatch_raw_observation(
            request.raw_payload_json,
            source_item_id=request.source_item_id,
            source_url=request.source_url,
        )
        if listing is None:
            return _error_response(
                ModuleError(
                    code="normalization_failed",
                    message="DropCatch raw observation could not be normalized.",
                    details={"source_item_id": request.source_item_id},
                )
            )

        domain = DomainIdentity(
            fqdn=listing.domain_name,
            sld=listing.sld,
            tld=listing.tld,
            punycode_fqdn=listing.domain_name,
            unicode_fqdn=listing.domain_name,
            is_valid=True,
        )
        auction = CanonicalAuction(
            marketplace_code=MarketplaceCode.DROPCATCH,
            source_item_id=request.source_item_id,
            source_url=request.source_url or listing.listing_url,
            auction_type=_map_auction_type(listing.auction_type),
            status=_map_status(listing.source_status),
            starts_at=None,
            ends_at=listing.close_time,
            current_bid=_copy_money(listing.current_price),
            min_bid=_copy_money(listing.min_next_bid),
            bid_count=listing.bid_count,
            watchers_count=None,
            normalized_payload_json={
                "source_name": self.source_name,
                "source_status": listing.source_status,
                "source_auction_type": listing.auction_type,
                "traffic": listing.traffic,
                "revenue": listing.revenue.to_api_dict() if listing.revenue else None,
                "renewal_price": listing.renewal_price.to_api_dict() if listing.renewal_price else None,
                "age_if_available": listing.age_if_available,
            },
        )
        snapshot = AuctionSnapshot(
            captured_at=request.captured_at,
            status=_map_status(listing.source_status),
            current_bid=_copy_money(listing.current_price),
            bid_count=listing.bid_count,
            watchers_count=None,
        )
        return NormalizeRawItemResponse(
            domain=domain,
            auction=auction,
            snapshot=snapshot,
            evidence_refs=[
                EvidenceRef(
                    type="raw_auction_item",
                    id=request.raw_auction_item_id,
                    source=self.source_name,
                    observed_at=request.captured_at,
                )
            ],
            errors=[],
        )


def _copy_money(value: Money | None) -> Money | None:
    if value is None:
        return None
    return Money(amount=value.amount, currency=value.currency)


def _map_status(source_status: str | None) -> AuctionStatus:
    normalized = (source_status or "").strip().lower()
    if any(token in normalized for token in ("active", "open", "live")):
        return AuctionStatus.OPEN
    if any(token in normalized for token in ("closing", "ending")):
        return AuctionStatus.CLOSING
    if any(token in normalized for token in ("scheduled", "upcoming")):
        return AuctionStatus.SCHEDULED
    if any(token in normalized for token in ("sold", "won")):
        return AuctionStatus.SOLD
    if "unsold" in normalized or "no sale" in normalized:
        return AuctionStatus.UNSOLD
    if any(token in normalized for token in ("closed", "ended")):
        return AuctionStatus.CLOSED
    if any(token in normalized for token in ("cancelled", "canceled")):
        return AuctionStatus.CANCELLED
    return AuctionStatus.UNKNOWN


def _map_auction_type(source_type: str | None) -> AuctionType:
    normalized = (source_type or "").strip().lower()
    if "closeout" in normalized:
        return AuctionType.CLOSEOUT
    if any(token in normalized for token in ("backorder", "dropcatch", "caught")):
        return AuctionType.BACKORDER
    if any(token in normalized for token in ("expired", "expiry", "deleting")):
        return AuctionType.EXPIRED
    if "registry" in normalized:
        return AuctionType.REGISTRY
    if any(token in normalized for token in ("private", "seller")):
        return AuctionType.PRIVATE_SELLER
    return AuctionType.UNKNOWN


def _error_response(error: ModuleError) -> NormalizeRawItemResponse:
    return NormalizeRawItemResponse(
        domain=None,
        auction=None,
        snapshot=None,
        evidence_refs=[],
        errors=[error],
    )
