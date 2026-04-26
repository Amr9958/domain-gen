"""DropCatch source-to-canonical auction normalization."""

from __future__ import annotations

from dataclasses import dataclass

from marketplaces.dropcatch.parser import MARKETPLACE_CODE, parse_domain_name
from marketplaces.schemas import (
    AdapterError,
    AuctionSnapshot,
    CanonicalAuction,
    DomainIdentity,
    EvidenceRef,
    Money,
    NormalizeRawItemRequest,
    NormalizeRawItemResponse,
)


@dataclass(frozen=True)
class DropCatchAuctionNormalizer:
    """Map DropCatch raw payloads into canonical domain, auction, and snapshot records."""

    def normalize_raw_item(self, request: NormalizeRawItemRequest) -> NormalizeRawItemResponse:
        payload = request.raw_payload_json
        if request.marketplace_code != MARKETPLACE_CODE:
            return _error_response(
                AdapterError(
                    code="schema_contract_mismatch",
                    message="DropCatch normalizer received a non-DropCatch marketplace code.",
                    details={"marketplace_code": request.marketplace_code},
                )
            )

        domain_name = str(payload.get("domain_name") or "").strip()
        parsed_domain = parse_domain_name(domain_name)
        if not parsed_domain:
            return _error_response(
                AdapterError(
                    code="domain_invalid",
                    message="DropCatch raw item cannot be normalized because the domain is invalid.",
                    details={"domain_name": domain_name},
                )
            )

        current_bid = _money_from_payload(payload.get("current_price"))
        min_bid = _money_from_payload(payload.get("min_next_bid"))
        status = _map_status(str(payload.get("source_status") or ""))
        auction_type = _map_auction_type(str(payload.get("auction_type") or ""))
        source_item_id = str(payload.get("source_listing_id") or "").strip()
        if not source_item_id:
            return _error_response(
                AdapterError(
                    code="source_payload_invalid",
                    message="DropCatch raw item is missing source_listing_id.",
                    details={"domain_name": domain_name},
                )
            )

        domain = DomainIdentity(
            fqdn=parsed_domain["fqdn"],
            sld=parsed_domain["sld"],
            tld=parsed_domain["tld"],
            punycode_fqdn=parsed_domain["punycode_fqdn"],
            unicode_fqdn=parsed_domain["unicode_fqdn"],
            is_valid=bool(parsed_domain["is_valid"]),
        )
        normalized_payload_json = {
            "source_name": payload.get("source_name"),
            "source_status": payload.get("source_status"),
            "source_auction_type": payload.get("auction_type"),
            "traffic": payload.get("traffic"),
            "revenue": payload.get("revenue"),
            "renewal_price": payload.get("renewal_price"),
            "age_if_available": payload.get("age_if_available"),
            "raw_payload": payload.get("raw_payload", {}),
        }
        auction = CanonicalAuction(
            marketplace_code=MARKETPLACE_CODE,
            source_item_id=source_item_id,
            source_url=str(payload.get("listing_url") or request.source_url or "") or None,
            auction_type=auction_type,
            status=status,
            starts_at=None,
            ends_at=str(payload.get("close_time") or "") or None,
            current_bid=current_bid,
            min_bid=min_bid,
            bid_count=_optional_int(payload.get("bid_count")),
            watchers_count=None,
            normalized_payload_json=normalized_payload_json,
        )
        snapshot = AuctionSnapshot(
            captured_at=request.captured_at,
            status=status,
            current_bid=current_bid,
            bid_count=_optional_int(payload.get("bid_count")),
            watchers_count=None,
        )
        evidence_ref = EvidenceRef(
            type="raw_auction_item",
            id=request.raw_auction_item_id,
            source=MARKETPLACE_CODE,
            observed_at=request.captured_at,
        )
        return NormalizeRawItemResponse(
            domain=domain,
            auction=auction,
            snapshot=snapshot,
            evidence_refs=[evidence_ref],
            errors=[],
        )


def _money_from_payload(value: object) -> Money | None:
    if not isinstance(value, dict):
        return None
    amount = str(value.get("amount") or "").strip()
    currency = str(value.get("currency") or "USD").strip().upper()
    if not amount:
        return None
    return Money(amount=amount, currency=currency or "USD")


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _map_status(source_status: str) -> str:
    normalized = source_status.strip().lower()
    if any(token in normalized for token in ("active", "open", "live")):
        return "open"
    if any(token in normalized for token in ("closing", "ending")):
        return "closing"
    if any(token in normalized for token in ("scheduled", "upcoming")):
        return "scheduled"
    if any(token in normalized for token in ("sold", "won")):
        return "sold"
    if "unsold" in normalized or "no sale" in normalized:
        return "unsold"
    if any(token in normalized for token in ("closed", "ended")):
        return "closed"
    if any(token in normalized for token in ("cancelled", "canceled")):
        return "cancelled"
    return "unknown"


def _map_auction_type(source_type: str) -> str:
    normalized = source_type.strip().lower()
    if "closeout" in normalized:
        return "closeout"
    if any(token in normalized for token in ("backorder", "dropcatch", "caught")):
        return "backorder"
    if any(token in normalized for token in ("expired", "expiry", "deleting")):
        return "expired"
    if "registry" in normalized:
        return "registry"
    if any(token in normalized for token in ("private", "seller")):
        return "private_seller"
    return "unknown"


def _error_response(error: AdapterError) -> NormalizeRawItemResponse:
    return NormalizeRawItemResponse(
        domain=None,
        auction=None,
        snapshot=None,
        evidence_refs=[],
        errors=[error],
    )
