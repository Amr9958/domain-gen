"""DropCatch-specific listing page parsing.

The parser is intentionally fixture-friendly and does not assume live access is
approved. It supports common HTML table/listing patterns and embedded JSON
payloads while preserving source fields that are not part of the canonical
auction schema.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from marketplaces.schemas import AdapterError, JsonDict, Money


MARKETPLACE_CODE = "dropcatch"
PARSER_VERSION = "dropcatch-parser-v1"
DEFAULT_CURRENCY = "USD"


@dataclass(frozen=True)
class DropCatchListing:
    """Source-level DropCatch listing record before canonical normalization."""

    source_name: str
    source_listing_id: str
    domain_name: str
    sld: str
    tld: str
    auction_type: str | None = None
    current_price: Money | None = None
    min_next_bid: Money | None = None
    bid_count: int | None = None
    close_time: str | None = None
    listing_url: str | None = None
    traffic: int | None = None
    revenue: Money | None = None
    renewal_price: Money | None = None
    age_if_available: int | None = None
    source_status: str | None = None
    raw_payload: JsonDict = field(default_factory=dict)

    def to_raw_payload_json(self) -> JsonDict:
        """Return a JSON-compatible payload that keeps source and parsed fields separate."""
        return {
            "source_name": self.source_name,
            "source_listing_id": self.source_listing_id,
            "domain_name": self.domain_name,
            "sld": self.sld,
            "tld": self.tld,
            "auction_type": self.auction_type,
            "current_price": self.current_price.to_dict() if self.current_price else None,
            "min_next_bid": self.min_next_bid.to_dict() if self.min_next_bid else None,
            "bid_count": self.bid_count,
            "close_time": self.close_time,
            "listing_url": self.listing_url,
            "traffic": self.traffic,
            "revenue": self.revenue.to_dict() if self.revenue else None,
            "renewal_price": self.renewal_price.to_dict() if self.renewal_price else None,
            "age_if_available": self.age_if_available,
            "source_status": self.source_status,
            "raw_payload": self.raw_payload,
        }


@dataclass(frozen=True)
class DropCatchPage:
    """Parsed DropCatch page with listing rows and traversal metadata."""

    listings: list[DropCatchListing]
    next_page_cursor: str | None = None
    errors: list[AdapterError] = field(default_factory=list)


class _ListingHTMLParser(HTMLParser):
    """Small table/script parser tailored to saved marketplace fixtures."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, Any]] = []
        self.links: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self._row: dict[str, Any] | None = None
        self._cell: dict[str, Any] | None = None
        self._anchor: dict[str, str] | None = None
        self._cell_depth = 0
        self._script_depth = 0
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()
        if tag == "tr":
            self._row = {"attrs": attr_map, "cells": []}
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = {"header": tag == "th", "text_parts": [], "links": [], "attrs": attr_map}
            self._cell_depth = 1
        elif tag == "a":
            self._anchor = {"href": attr_map.get("href", ""), "rel": attr_map.get("rel", ""), "text": ""}
            if self._cell is not None and self._anchor["href"]:
                self._cell["links"].append(self._anchor["href"])
        elif tag == "script":
            self._script_depth = 1
            self._script_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"th", "td"} and self._cell is not None:
            text = " ".join("".join(self._cell["text_parts"]).split())
            self._cell["text"] = text
            self._row["cells"].append(self._cell)
            self._cell = None
            self._cell_depth = 0
        elif tag == "tr" and self._row is not None:
            if self._row["cells"]:
                self.rows.append(self._row)
            self._row = None
        elif tag == "a" and self._anchor is not None:
            self.links.append(self._anchor)
            self._anchor = None
        elif tag == "script" and self._script_depth:
            script_text = "".join(self._script_parts).strip()
            if script_text:
                self.scripts.append(script_text)
            self._script_depth = 0
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None and self._cell_depth:
            self._cell["text_parts"].append(data)
        if self._anchor is not None:
            self._anchor["text"] = f"{self._anchor.get('text', '')}{data}"
        if self._script_depth:
            self._script_parts.append(data)


def parse_listing_page(html: str, *, page_url: str) -> DropCatchPage:
    """Parse a DropCatch listing page fixture into source listings."""
    parser = _ListingHTMLParser()
    parser.feed(html)

    listings: list[DropCatchListing] = []
    errors: list[AdapterError] = []

    for raw_item in _extract_json_listing_candidates(parser.scripts):
        listing, error = _listing_from_mapping(raw_item, page_url=page_url)
        if listing:
            listings.append(listing)
        elif error:
            errors.append(error)

    if not listings:
        table_listings, table_errors = _extract_table_listings(parser.rows, page_url=page_url)
        listings.extend(table_listings)
        errors.extend(table_errors)

    return DropCatchPage(
        listings=_dedupe_listings(listings),
        next_page_cursor=_extract_next_page_cursor(parser.links, page_url),
        errors=errors,
    )


def _extract_table_listings(rows: list[dict[str, Any]], *, page_url: str) -> tuple[list[DropCatchListing], list[AdapterError]]:
    headers: list[str] = []
    listings: list[DropCatchListing] = []
    errors: list[AdapterError] = []

    for row in rows:
        cells = row.get("cells", [])
        if not cells:
            continue
        if all(cell.get("header") for cell in cells):
            headers = [_normalize_header(str(cell.get("text") or "")) for cell in cells]
            continue

        values = [str(cell.get("text") or "").strip() for cell in cells]
        row_payload: JsonDict = {
            "attrs": row.get("attrs", {}),
            "headers": headers,
            "cells": values,
            "links": [link for cell in cells for link in cell.get("links", [])],
            "parser_version": PARSER_VERSION,
        }
        mapped = _map_table_row(headers, values, cells, row.get("attrs", {}), page_url)
        listing, error = _listing_from_mapping(mapped, page_url=page_url, raw_payload=row_payload)
        if listing:
            listings.append(listing)
        elif error:
            errors.append(error)

    return listings, errors


def _map_table_row(
    headers: list[str],
    values: list[str],
    cells: list[dict[str, Any]],
    row_attrs: dict[str, str],
    page_url: str,
) -> JsonDict:
    if not headers:
        headers = [
            "domain",
            "currentprice",
            "minnextbid",
            "bidcount",
            "closetime",
            "status",
            "auctiontype",
        ][: len(values)]

    field_map = {_canonical_field_name(header): value for header, value in zip(headers, values)}
    first_link = next((link for cell in cells for link in cell.get("links", []) if link), "")
    if first_link:
        field_map.setdefault("listing_url", urljoin(page_url, first_link))

    for attr_name in ("data-id", "data-listing-id", "data-auction-id", "id"):
        if row_attrs.get(attr_name):
            field_map.setdefault("source_listing_id", row_attrs[attr_name])
            break
    if row_attrs.get("data-domain"):
        field_map.setdefault("domain_name", row_attrs["data-domain"])

    return field_map


def _listing_from_mapping(
    payload: JsonDict,
    *,
    page_url: str,
    raw_payload: JsonDict | None = None,
) -> tuple[DropCatchListing | None, AdapterError | None]:
    domain_name = _first_text(payload, "domain_name", "domain", "name", "domainName")
    domain_identity = parse_domain_name(domain_name)
    if not domain_identity:
        return None, AdapterError(
            code="source_payload_invalid",
            message="DropCatch listing row did not contain a valid domain name.",
            details={"payload_keys": sorted(payload.keys())},
        )

    listing_url = _first_text(payload, "listing_url", "url", "source_url", "auctionUrl", "detailUrl")
    if listing_url:
        listing_url = urljoin(page_url, listing_url)

    source_listing_id = _first_text(
        payload,
        "source_listing_id",
        "sourceListingId",
        "listingId",
        "auctionId",
        "id",
    )
    if not source_listing_id:
        source_listing_id = _source_id_from_listing_url(listing_url) or domain_identity["fqdn"]

    raw = raw_payload or {**payload, "parser_version": PARSER_VERSION}
    return (
        DropCatchListing(
            source_name=MARKETPLACE_CODE,
            source_listing_id=str(source_listing_id).strip(),
            domain_name=domain_identity["fqdn"],
            sld=domain_identity["sld"],
            tld=domain_identity["tld"],
            auction_type=_first_text(payload, "auction_type", "auctionType", "type"),
            current_price=_parse_money(_first_text(payload, "current_price", "currentBid", "currentPrice", "price")),
            min_next_bid=_parse_money(_first_text(payload, "min_next_bid", "minNextBid", "nextBid", "minimumBid")),
            bid_count=_parse_int(_first_text(payload, "bid_count", "bidCount", "bids")),
            close_time=_parse_datetime_text(_first_text(payload, "close_time", "closeTime", "endTime", "endsAt")),
            listing_url=listing_url,
            traffic=_parse_int(_first_text(payload, "traffic", "visits")),
            revenue=_parse_money(_first_text(payload, "revenue", "monthlyRevenue")),
            renewal_price=_parse_money(_first_text(payload, "renewal_price", "renewalPrice")),
            age_if_available=_parse_int(_first_text(payload, "age_if_available", "age", "domainAge")),
            source_status=_first_text(payload, "source_status", "status", "auctionStatus"),
            raw_payload=raw,
        ),
        None,
    )


def parse_domain_name(value: str | None) -> JsonDict | None:
    """Parse a domain name into simple fqdn/sld/tld parts using IDNA."""
    if not value:
        return None
    candidate = str(value).strip().lower()
    candidate = re.sub(r"^https?://", "", candidate)
    candidate = candidate.split("/")[0].strip(".")
    if "." not in candidate:
        return None
    try:
        punycode = candidate.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    labels = punycode.split(".")
    if len(labels) < 2 or any(not label for label in labels):
        return None
    if not all(re.fullmatch(r"[a-z0-9-]{1,63}", label) for label in labels):
        return None
    if labels[-1].startswith("-") or labels[-1].endswith("-"):
        return None
    unicode_fqdn = punycode.encode("ascii").decode("idna")
    return {
        "fqdn": punycode,
        "sld": labels[-2],
        "tld": labels[-1],
        "punycode_fqdn": punycode,
        "unicode_fqdn": unicode_fqdn,
        "is_valid": True,
    }


def _extract_json_listing_candidates(scripts: list[str]) -> list[JsonDict]:
    candidates: list[JsonDict] = []
    for script in scripts:
        text = script.strip()
        if not text or not ("domain" in text.lower() or "auction" in text.lower()):
            continue
        parsed = _parse_possible_json_script(text)
        if parsed is None:
            continue
        candidates.extend(_walk_json_for_listings(parsed))
    return candidates


def _parse_possible_json_script(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"({.*})", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _walk_json_for_listings(value: Any) -> list[JsonDict]:
    listings: list[JsonDict] = []
    if isinstance(value, list):
        for item in value:
            listings.extend(_walk_json_for_listings(item))
    elif isinstance(value, dict):
        if _looks_like_listing_dict(value):
            listings.append(value)
        for child in value.values():
            if isinstance(child, (dict, list)):
                listings.extend(_walk_json_for_listings(child))
    return listings


def _looks_like_listing_dict(value: dict[str, Any]) -> bool:
    keys = {_normalize_header(str(key)) for key in value.keys()}
    has_domain = bool(keys & {"domain", "domainname", "name"})
    has_auction_data = bool(
        keys
        & {
            "currentbid",
            "currentprice",
            "price",
            "minnextbid",
            "nextbid",
            "endtime",
            "closetime",
            "bidcount",
            "auctionid",
            "listingid",
        }
    )
    return has_domain and has_auction_data


def _extract_next_page_cursor(links: list[dict[str, str]], page_url: str) -> str | None:
    for link in links:
        rel = str(link.get("rel") or "").lower()
        text = " ".join(str(link.get("text") or "").lower().split())
        href = str(link.get("href") or "").strip()
        if not href:
            continue
        if "next" in rel or text in {"next", "next page", ">"}:
            return urljoin(page_url, href)
    return None


def _dedupe_listings(listings: list[DropCatchListing]) -> list[DropCatchListing]:
    seen: set[tuple[str, str]] = set()
    unique: list[DropCatchListing] = []
    for listing in listings:
        key = (listing.source_name, listing.source_listing_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(listing)
    return unique


def _first_text(payload: JsonDict, *keys: str) -> str | None:
    normalized = {_normalize_header(str(key)): value for key, value in payload.items()}
    for key in keys:
        value = normalized.get(_normalize_header(key))
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"none", "null", "n/a", "na", "-"}:
            return text
    return None


def _canonical_field_name(header: str) -> str:
    normalized = _normalize_header(header)
    mapping = {
        "domain": "domain_name",
        "domainname": "domain_name",
        "name": "domain_name",
        "currentbid": "current_price",
        "currentprice": "current_price",
        "highbid": "current_price",
        "price": "current_price",
        "minnextbid": "min_next_bid",
        "nextbid": "min_next_bid",
        "minimumbid": "min_next_bid",
        "bids": "bid_count",
        "bidcount": "bid_count",
        "ending": "close_time",
        "endtime": "close_time",
        "endsat": "close_time",
        "closetime": "close_time",
        "status": "source_status",
        "auctionstatus": "source_status",
        "type": "auction_type",
        "auctiontype": "auction_type",
        "traffic": "traffic",
        "visits": "traffic",
        "revenue": "revenue",
        "monthlyrevenue": "revenue",
        "renewal": "renewal_price",
        "renewalprice": "renewal_price",
        "age": "age_if_available",
        "domainage": "age_if_available",
        "listingid": "source_listing_id",
        "auctionid": "source_listing_id",
    }
    return mapping.get(normalized, normalized)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _source_id_from_listing_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"([A-Za-z0-9_-]+)(?:/?(?:\?.*)?)$", url)
    return match.group(1) if match else None


def _parse_money(value: str | None) -> Money | None:
    if not value:
        return None
    currency = DEFAULT_CURRENCY
    text = str(value).strip()
    if "usd" in text.lower() or "$" in text:
        currency = "USD"
    numeric = re.sub(r"[^0-9.]", "", text)
    if not numeric:
        return None
    try:
        amount = Decimal(numeric).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return Money(amount=f"{amount:.2f}", currency=currency)


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d[\d,]*", str(value))
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _parse_datetime_text(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).strip().split())
    iso_candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        return _datetime_to_utc_iso(parsed)
    except ValueError:
        pass

    formats = [
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return _datetime_to_utc_iso(parsed.replace(tzinfo=timezone.utc))
        except ValueError:
            continue
    return None


def _datetime_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
