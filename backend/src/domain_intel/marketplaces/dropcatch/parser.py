"""DropCatch listing-page parsing helpers."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from domain_intel.marketplaces.schemas import ModuleError, Money


SOURCE_NAME = "dropcatch"
PARSER_VERSION = "dropcatch-parser-v1"
DEFAULT_CURRENCY = "USD"


@dataclass(frozen=True)
class DropCatchParsedListing:
    """Source-level DropCatch listing before canonical normalization."""

    source_name: str
    source_listing_id: str
    domain_name: str
    sld: str
    tld: str
    auction_type: str | None = None
    current_price: Money | None = None
    min_next_bid: Money | None = None
    bid_count: int | None = None
    close_time: datetime | None = None
    listing_url: str | None = None
    traffic: int | None = None
    revenue: Money | None = None
    renewal_price: Money | None = None
    age_if_available: int | None = None
    source_status: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DropCatchParsedPage:
    """Parsed DropCatch page with listing rows and traversal metadata."""

    listings: list[DropCatchParsedListing]
    next_page_cursor: str | None = None
    errors: list[ModuleError] = field(default_factory=list)


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
        self._script_depth = 0
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()
        if tag == "tr":
            self._row = {"attrs": attr_map, "cells": []}
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = {"header": tag == "th", "text_parts": [], "links": [], "attrs": attr_map}
        elif tag == "a":
            self._anchor = {"href": attr_map.get("href", ""), "rel": attr_map.get("rel", ""), "text": ""}
            if self._cell is not None and self._anchor["href"]:
                self._cell["links"].append(self._anchor["href"])
        elif tag == "script":
            self._script_depth = 1
            self._script_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell["text_parts"]).split())
            self._cell["text"] = text
            self._row["cells"].append(self._cell)
            self._cell = None
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
        if self._cell is not None:
            self._cell["text_parts"].append(data)
        if self._anchor is not None:
            self._anchor["text"] = f"{self._anchor.get('text', '')}{data}"
        if self._script_depth:
            self._script_parts.append(data)


def parse_dropcatch_listing_page(html: str, *, page_url: str) -> DropCatchParsedPage:
    """Parse one DropCatch listing page fixture into source listings."""

    parser = _ListingHTMLParser()
    parser.feed(html)

    listings: list[DropCatchParsedListing] = []
    errors: list[ModuleError] = []

    for raw_item in _extract_json_listing_candidates(parser.scripts):
        listing, error = _listing_from_mapping(
            raw_item,
            page_url=page_url,
            raw_payload={
                "extraction_method": "structured_json",
                "record": raw_item,
                "page_url": page_url,
                "parser_version": PARSER_VERSION,
            },
        )
        if listing:
            listings.append(listing)
        elif error:
            errors.append(error)

    if not listings:
        table_listings, table_errors = _extract_table_listings(parser.rows, page_url=page_url)
        listings.extend(table_listings)
        errors.extend(table_errors)

    return DropCatchParsedPage(
        listings=_dedupe_listings(listings),
        next_page_cursor=_extract_next_page_cursor(parser.links, page_url),
        errors=errors,
    )


def parse_dropcatch_raw_observation(
    raw_payload: Mapping[str, Any],
    *,
    source_item_id: str,
    source_url: str | None,
) -> DropCatchParsedListing | None:
    """Reconstruct a parsed DropCatch listing from stored raw observation payload."""

    extraction_method = _first_text(raw_payload, "extraction_method")
    page_url = _first_text(raw_payload, "page_url") or source_url or "https://www.dropcatch.com"
    if extraction_method == "structured_json":
        record = raw_payload.get("record")
        if not isinstance(record, dict):
            return None
        listing, _ = _listing_from_mapping(record, page_url=page_url, raw_payload=raw_payload)
        if listing is None:
            return None
        return DropCatchParsedListing(
            source_name=listing.source_name,
            source_listing_id=source_item_id or listing.source_listing_id,
            domain_name=listing.domain_name,
            sld=listing.sld,
            tld=listing.tld,
            auction_type=listing.auction_type,
            current_price=listing.current_price,
            min_next_bid=listing.min_next_bid,
            bid_count=listing.bid_count,
            close_time=listing.close_time,
            listing_url=source_url or listing.listing_url,
            traffic=listing.traffic,
            revenue=listing.revenue,
            renewal_price=listing.renewal_price,
            age_if_available=listing.age_if_available,
            source_status=listing.source_status,
            raw_payload=raw_payload,
        )

    if extraction_method == "html_table":
        headers = raw_payload.get("headers")
        cells = raw_payload.get("cells")
        row_attrs = raw_payload.get("attrs")
        if not isinstance(cells, list):
            return None
        mapped = _map_table_row(
            [str(value) for value in headers] if isinstance(headers, list) else [],
            [str(value) for value in cells],
            _cells_from_raw_payload(raw_payload),
            {str(key): str(value) for key, value in row_attrs.items()} if isinstance(row_attrs, Mapping) else {},
            page_url,
        )
        listing, _ = _listing_from_mapping(mapped, page_url=page_url, raw_payload=raw_payload)
        if listing is None:
            return None
        return DropCatchParsedListing(
            source_name=listing.source_name,
            source_listing_id=source_item_id or listing.source_listing_id,
            domain_name=listing.domain_name,
            sld=listing.sld,
            tld=listing.tld,
            auction_type=listing.auction_type,
            current_price=listing.current_price,
            min_next_bid=listing.min_next_bid,
            bid_count=listing.bid_count,
            close_time=listing.close_time,
            listing_url=source_url or listing.listing_url,
            traffic=listing.traffic,
            revenue=listing.revenue,
            renewal_price=listing.renewal_price,
            age_if_available=listing.age_if_available,
            source_status=listing.source_status,
            raw_payload=raw_payload,
        )

    return None


def parse_domain_name(value: str | None) -> dict[str, Any] | None:
    """Parse a domain name into fqdn/sld/tld parts using IDNA."""

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


def _extract_table_listings(rows: list[dict[str, Any]], *, page_url: str) -> tuple[list[DropCatchParsedListing], list[ModuleError]]:
    headers: list[str] = []
    listings: list[DropCatchParsedListing] = []
    errors: list[ModuleError] = []

    for row in rows:
        cells = row.get("cells", [])
        if not cells:
            continue
        if all(cell.get("header") for cell in cells):
            headers = [_normalize_header(str(cell.get("text") or "")) for cell in cells]
            continue

        values = [str(cell.get("text") or "").strip() for cell in cells]
        row_payload: dict[str, Any] = {
            "extraction_method": "html_table",
            "attrs": row.get("attrs", {}),
            "headers": headers,
            "cells": values,
            "links": [link for cell in cells for link in cell.get("links", [])],
            "page_url": page_url,
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
) -> dict[str, Any]:
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
    payload: dict[str, Any],
    *,
    page_url: str,
    raw_payload: Mapping[str, Any],
) -> tuple[DropCatchParsedListing | None, ModuleError | None]:
    domain_name = _first_text(payload, "domain_name", "domain", "name", "domainName")
    domain_identity = parse_domain_name(domain_name)
    if not domain_identity:
        return None, ModuleError(
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

    return (
        DropCatchParsedListing(
            source_name=SOURCE_NAME,
            source_listing_id=str(source_listing_id).strip(),
            domain_name=domain_identity["fqdn"],
            sld=domain_identity["sld"],
            tld=domain_identity["tld"],
            auction_type=_first_text(payload, "auction_type", "auctionType", "type"),
            current_price=_parse_money(_first_text(payload, "current_price", "currentBid", "currentPrice", "price")),
            min_next_bid=_parse_money(_first_text(payload, "min_next_bid", "minNextBid", "nextBid", "minimumBid")),
            bid_count=_parse_int(_first_text(payload, "bid_count", "bidCount", "bids")),
            close_time=_parse_datetime(_first_text(payload, "close_time", "closeTime", "endTime", "endsAt")),
            listing_url=listing_url,
            traffic=_parse_int(_first_text(payload, "traffic", "visits")),
            revenue=_parse_money(_first_text(payload, "revenue", "monthlyRevenue")),
            renewal_price=_parse_money(_first_text(payload, "renewal_price", "renewalPrice")),
            age_if_available=_parse_int(_first_text(payload, "age_if_available", "age", "domainAge")),
            source_status=_first_text(payload, "source_status", "status", "auctionStatus"),
            raw_payload=raw_payload,
        ),
        None,
    )


def _extract_json_listing_candidates(scripts: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for script in scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        candidates.extend(_find_listing_mappings(payload))
    return candidates


def _find_listing_mappings(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if parse_domain_name(_first_text(payload, "domain_name", "domain", "name", "domainName")):
            return [payload]
        matches: list[dict[str, Any]] = []
        for value in payload.values():
            matches.extend(_find_listing_mappings(value))
        return matches
    if isinstance(payload, list):
        matches: list[dict[str, Any]] = []
        for item in payload:
            matches.extend(_find_listing_mappings(item))
        return matches
    return []


def _dedupe_listings(listings: list[DropCatchParsedListing]) -> list[DropCatchParsedListing]:
    deduped: list[DropCatchParsedListing] = []
    seen: set[str] = set()
    for listing in listings:
        if listing.source_listing_id in seen:
            continue
        seen.add(listing.source_listing_id)
        deduped.append(listing)
    return deduped


def _extract_next_page_cursor(links: list[dict[str, str]], page_url: str) -> str | None:
    for link in links:
        text = " ".join([link.get("text", ""), link.get("rel", "")]).strip().lower()
        href = link.get("href") or ""
        if href and "next" in text:
            return urljoin(page_url, href)
    return None


def _source_id_from_listing_url(listing_url: str | None) -> str | None:
    if not listing_url:
        return None
    slug = listing_url.rstrip("/").split("/")[-1]
    return slug or None


def _first_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    normalized = {_normalize_header(str(key)): value for key, value in payload.items()}
    for key in keys:
        value = normalized.get(_normalize_header(key))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_money(value: str | None) -> Money | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    currency = DEFAULT_CURRENCY
    if candidate.upper().endswith(" EUR") or "€" in candidate:
        currency = "EUR"
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", candidate)
    if not match:
        return None
    try:
        amount = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    return Money(amount=amount, currency=currency)


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    match = re.search(r"-?\d[\d,]*", candidate)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    candidate = value.strip().replace("Z", "+00:00")
    if not candidate:
        return None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_field_name(header: str) -> str:
    normalized = _normalize_header(header)
    aliases = {
        "domain": "domain_name",
        "currentprice": "current_price",
        "currentbid": "current_price",
        "price": "current_price",
        "minnextbid": "min_next_bid",
        "nextbid": "min_next_bid",
        "bidcount": "bid_count",
        "bids": "bid_count",
        "closetime": "close_time",
        "endtime": "close_time",
        "status": "source_status",
        "auctionstatus": "source_status",
        "auctiontype": "auction_type",
        "type": "auction_type",
        "traffic": "traffic",
        "visits": "traffic",
        "revenue": "revenue",
        "monthlyrevenue": "revenue",
        "renewalprice": "renewal_price",
        "age": "age_if_available",
        "domainage": "age_if_available",
    }
    return aliases.get(normalized, normalized)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _cells_from_raw_payload(raw_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    cells = raw_payload.get("cells")
    links = raw_payload.get("links")
    if not isinstance(cells, list):
        return []
    link_values = list(links) if isinstance(links, list) else []
    rebuilt: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        cell_links = []
        if index == 0 and link_values:
            cell_links = [str(value) for value in link_values if value]
        rebuilt.append({"text": str(cell), "links": cell_links, "attrs": {}, "header": False})
    return rebuilt
