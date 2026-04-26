"""Dynadot raw-observation normalization."""

from __future__ import annotations

from domain_intel.core.enums import MarketplaceCode
from domain_intel.marketplaces.dynadot.parser import SOURCE_NAME, parse_dynadot_raw_observation
from domain_intel.marketplaces.schemas import ModuleError, Money
from domain_intel.normalization.schemas import (
    AuctionSnapshot,
    CanonicalAuction,
    DomainIdentity,
    EvidenceRef,
    NormalizeRawItemRequest,
    NormalizeRawItemResponse,
)


class DynadotAuctionNormalizer:
    """Map stored Dynadot raw observations into canonical auction payloads."""

    source_name = SOURCE_NAME

    def normalize_raw_item(self, request: NormalizeRawItemRequest) -> NormalizeRawItemResponse:
        marketplace_code = str(request.marketplace_code.value if hasattr(request.marketplace_code, "value") else request.marketplace_code)
        if marketplace_code != MarketplaceCode.DYNADOT.value:
            return _error_response(
                ModuleError(
                    code="schema_contract_mismatch",
                    message="Dynadot normalizer only accepts marketplace_code=dynadot.",
                    details={"marketplace_code": marketplace_code},
                )
            )

        listing = parse_dynadot_raw_observation(
            request.raw_payload_json,
            source_item_id=request.source_item_id,
            source_url=request.source_url,
            captured_at=request.captured_at,
        )
        if listing is None:
            return _error_response(
                ModuleError(
                    code="normalization_failed",
                    message="Dynadot raw observation could not be normalized.",
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
            marketplace_code=MarketplaceCode.DYNADOT,
            source_item_id=request.source_item_id,
            source_url=request.source_url or listing.listing_url,
            auction_type=listing.auction_type,
            status=listing.canonical_status,
            starts_at=None,
            ends_at=listing.close_time,
            current_bid=_copy_money(listing.current_price),
            min_bid=_copy_money(listing.min_next_bid),
            bid_count=listing.bid_count,
            watchers_count=None,
            normalized_payload_json={
                "source_name": self.source_name,
                "source_status": listing.source_status,
                "traffic": listing.traffic,
                "revenue": listing.revenue.to_api_dict() if listing.revenue else None,
                "renewal_price": listing.renewal_price.to_api_dict() if listing.renewal_price else None,
                "age_if_available": listing.age_if_available,
            },
        )
        snapshot = AuctionSnapshot(
            captured_at=request.captured_at,
            status=listing.canonical_status,
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


def _error_response(error: ModuleError) -> NormalizeRawItemResponse:
    return NormalizeRawItemResponse(
        domain=None,
        auction=None,
        snapshot=None,
        evidence_refs=[],
        errors=[error],
    )
