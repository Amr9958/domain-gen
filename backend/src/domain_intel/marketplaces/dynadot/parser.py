"""Dynadot auction page parser.

Parsing is intentionally isolated in this module so source-specific HTML and
embedded JSON handling do not leak into shared marketplace code.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from domain_intel.core.enums import AuctionStatus, AuctionType
from domain_intel.marketplaces.schemas import Money, NormalizedAuctionListing


PARSER_VERSION = "dynadot-parser-v1"
SOURCE_NAME = "dynadot"


HEADER_ALIASES = {
    "domain": ("domain", "domainname", "name"),
    "current_price": ("currentbid", "currentprice", "price", "bid"),
    "min_next_bid": ("nextbid", "minbid", "minimumbid", "minnextbid"),
    "bid_count": ("bids", "bidcount", "bid_count"),
    "close_time": ("timeleft", "endtime", "enddate", "endsat", "closetime", "close"),
    "traffic": ("traffic", "visitors", "monthlyvisitors", "views"),
    "revenue": ("revenue", "monthlyrevenue"),
    "renewal_price": ("renewal", "renewalprice", "renewprice"),
    "age_if_available": ("age", "domainage", "ageyears"),
    "source_status": ("status", "auctionstatus"),
    "auction_type": ("type", "auctiontype"),
}

DEFAULT_COLUMN_ORDER = (
    "domain",
    "close_time",
    "current_price",
    "min_next_bid",
    "bid_count",
    "traffic",
    "revenue",
    "renewal_price",
    "age_if_available",
    "source_status",
)


@dataclass(frozen=True)
class DynadotParsedListing:
    """Dynadot-specific parsed listing before persistence."""

    source_listing_id: str
    domain_name: str
    sld: str
    tld: str
    auction_type: AuctionType
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
    canonical_status: AuctionStatus
    raw_payload: Mapping[str, Any]

    def to_normalized(self) -> NormalizedAuctionListing:
        return NormalizedAuctionListing(
            source_name=SOURCE_NAME,
            source_listing_id=self.source_listing_id,
            domain_name=self.domain_name,
            sld=self.sld,
            tld=self.tld,
            auction_type=self.auction_type,
            current_price=self.current_price,
            min_next_bid=self.min_next_bid,
            bid_count=self.bid_count,
            close_time=self.close_time,
            listing_url=self.listing_url,
            traffic=self.traffic,
            revenue=self.revenue,
            renewal_price=self.renewal_price,
            age_if_available=self.age_if_available,
            source_status=self.source_status,
            canonical_status=self.canonical_status,
            raw_payload=self.raw_payload,
        )


@dataclass(frozen=True)
class DynadotParsedPage:
    """Parsed Dynadot page result."""

    listings: list[DynadotParsedListing]
    next_page_cursor: str | None


@dataclass
class _Link:
    attrs: dict[str, str]
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return _collapse_text(" ".join(self.text_parts))


@dataclass
class _Cell:
    tag: str
    attrs: dict[str, str]
    text_parts: list[str] = field(default_factory=list)
    links: list[_Link] = field(default_factory=list)

    @property
    def text(self) -> str:
        return _collapse_text(" ".join(self.text_parts))


@dataclass
class _Row:
    attrs: dict[str, str]
    cells: list[_Cell] = field(default_factory=list)


class _DynadotHTMLParser(HTMLParser):
    """Small HTML collector for tables, links, and embedded JSON scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[_Row] = []
        self.links: list[_Link] = []
        self.scripts: list[str] = []
        self._current_row: _Row | None = None
        self._current_cell: _Cell | None = None
        self._current_link: _Link | None = None
        self._current_script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        tag_name = tag.lower()

        if tag_name == "script" and self._is_json_script(attr_map):
            self._current_script = []
            return
        if tag_name == "tr":
            self._current_row = _Row(attrs=attr_map)
            return
        if tag_name in {"td", "th"} and self._current_row is not None:
            self._current_cell = _Cell(tag=tag_name, attrs=attr_map)
            return
        if tag_name == "a":
            link = _Link(attrs=attr_map)
            self.links.append(link)
            self._current_link = link
            if self._current_cell is not None:
                self._current_cell.links.append(link)

    def handle_data(self, data: str) -> None:
        if self._current_script is not None:
            self._current_script.append(data)
            return
        if self._current_cell is not None:
            self._current_cell.text_parts.append(data)
        if self._current_link is not None:
            self._current_link.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "script" and self._current_script is not None:
            script = "".join(self._current_script).strip()
            if script:
                self.scripts.append(script)
            self._current_script = None
            return
        if tag_name in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.cells.append(self._current_cell)
            self._current_cell = None
            return
        if tag_name == "tr" and self._current_row is not None:
            if self._current_row.cells:
                self.rows.append(self._current_row)
            self._current_row = None
            self._current_cell = None
            return
        if tag_name == "a":
            self._current_link = None

    @staticmethod
    def _is_json_script(attrs: Mapping[str, str]) -> bool:
        script_type = attrs.get("type", "").lower()
        script_id = attrs.get("id", "").lower()
        return "json" in script_type or script_id == "__next_data__"


def parse_dynadot_listing_page(
    html_text: str,
    *,
    page_url: str,
    captured_at: datetime | None = None,
) -> DynadotParsedPage:
    """Parse one Dynadot auction listing page without making network calls."""

    parser = _DynadotHTMLParser()
    parser.feed(html_text)
    parsed_at = _ensure_utc(captured_at or datetime.now(timezone.utc))

    listings: list[DynadotParsedListing] = []
    seen_listing_ids: set[str] = set()

    for listing in _parse_structured_listings(parser.scripts, page_url=page_url, captured_at=parsed_at):
        if listing.source_listing_id not in seen_listing_ids:
            listings.append(listing)
            seen_listing_ids.add(listing.source_listing_id)

    for listing in _parse_table_listings(parser.rows, page_url=page_url, captured_at=parsed_at):
        if listing.source_listing_id not in seen_listing_ids:
            listings.append(listing)
            seen_listing_ids.add(listing.source_listing_id)

    return DynadotParsedPage(
        listings=listings,
        next_page_cursor=_extract_next_page_cursor(parser.links, parser.scripts, page_url),
    )


def _parse_table_listings(
    rows: Iterable[_Row],
    *,
    page_url: str,
    captured_at: datetime,
) -> list[DynadotParsedListing]:
    listings: list[DynadotParsedListing] = []
    headers: list[str] | None = None

    for row in rows:
        if row.cells and all(cell.tag == "th" for cell in row.cells):
            headers = [_normalize_key(cell.text) for cell in row.cells]
            continue

        field_cells: dict[str, _Cell] = {}
        if headers:
            for index, cell in enumerate(row.cells):
                if index < len(headers):
                    field_cells[headers[index]] = cell
        else:
            for index, cell in enumerate(row.cells):
                if index < len(DEFAULT_COLUMN_ORDER):
                    field_cells[_normalize_key(DEFAULT_COLUMN_ORDER[index])] = cell

        listing = _listing_from_cells(row, field_cells, page_url=page_url, captured_at=captured_at)
        if listing is not None:
            listings.append(listing)

    return listings


def _listing_from_cells(
    row: _Row,
    field_cells: Mapping[str, _Cell],
    *,
    page_url: str,
    captured_at: datetime,
) -> DynadotParsedListing | None:
    domain_cell = _cell_by_alias(field_cells, HEADER_ALIASES["domain"])
    if domain_cell is None:
        domain_cell = next((cell for cell in row.cells if _looks_like_domain(_clean_domain(cell.text))), None)
    if domain_cell is None:
        return None

    domain_name = _clean_domain(domain_cell.text)
    if not _looks_like_domain(domain_name):
        return None

    listing_url = _first_listing_url(domain_cell.links, page_url)
    source_listing_id = _row_source_id(row.attrs, listing_url, domain_name)
    sld, tld = _split_domain(domain_name)
    close_cell = _cell_by_alias(field_cells, HEADER_ALIASES["close_time"])
    close_time = _parse_close_time(
        close_cell.attrs.get("data-close-time") if close_cell else None,
        close_cell.text if close_cell else None,
        captured_at=captured_at,
    )
    source_status = _cell_text(field_cells, HEADER_ALIASES["source_status"])
    auction_type_text = _cell_text(field_cells, HEADER_ALIASES["auction_type"])

    raw_cells = {
        key: {
            "text": cell.text,
            "attributes": cell.attrs,
            "links": [
                {
                    "href": link.attrs.get("href"),
                    "text": link.text,
                    "attributes": link.attrs,
                }
                for link in cell.links
            ],
        }
        for key, cell in field_cells.items()
    }
    return DynadotParsedListing(
        source_listing_id=source_listing_id,
        domain_name=domain_name,
        sld=sld,
        tld=tld,
        auction_type=_map_auction_type(auction_type_text, page_url),
        current_price=_parse_money(_cell_text(field_cells, HEADER_ALIASES["current_price"])),
        min_next_bid=_parse_money(_cell_text(field_cells, HEADER_ALIASES["min_next_bid"])),
        bid_count=_parse_int(_cell_text(field_cells, HEADER_ALIASES["bid_count"])),
        close_time=close_time,
        listing_url=listing_url,
        traffic=_parse_int(_cell_text(field_cells, HEADER_ALIASES["traffic"])),
        revenue=_parse_money(_cell_text(field_cells, HEADER_ALIASES["revenue"])),
        renewal_price=_parse_money(_cell_text(field_cells, HEADER_ALIASES["renewal_price"])),
        age_if_available=_parse_int(_cell_text(field_cells, HEADER_ALIASES["age_if_available"])),
        source_status=source_status,
        canonical_status=_map_status(source_status, close_time=close_time, captured_at=captured_at),
        raw_payload={
            "extraction_method": "html_table",
            "row_attributes": row.attrs,
            "cells": raw_cells,
            "page_url": page_url,
        },
    )


def _parse_structured_listings(
    scripts: Iterable[str],
    *,
    page_url: str,
    captured_at: datetime,
) -> list[DynadotParsedListing]:
    listings: list[DynadotParsedListing] = []
    for script in scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        for candidate in _iter_candidate_mappings(payload):
            listing = _listing_from_mapping(candidate, page_url=page_url, captured_at=captured_at)
            if listing is not None:
                listings.append(listing)
    return listings


def _listing_from_mapping(
    payload: Mapping[str, Any],
    *,
    page_url: str,
    captured_at: datetime,
) -> DynadotParsedListing | None:
    domain_name = _clean_domain(_lookup(payload, ("domainName", "domain_name", "domain", "name", "fqdn")))
    if not _looks_like_domain(domain_name):
        return None

    listing_url = _absolute_url(
        _lookup(payload, ("listingUrl", "listing_url", "auctionUrl", "url", "href")),
        page_url,
    )
    source_listing_id = str(
        _lookup(payload, ("sourceListingId", "auctionId", "auction_id", "listingId", "listing_id", "id"))
        or _source_id_from_url(listing_url)
        or domain_name
    )
    close_time = _parse_close_time(
        _lookup(payload, ("closeTime", "close_time", "endTime", "end_time", "endsAt", "ends_at", "endDate")),
        None,
        captured_at=captured_at,
    )
    source_status = _string_or_none(_lookup(payload, ("status", "auctionStatus", "sourceStatus")))
    auction_type_text = _string_or_none(_lookup(payload, ("auctionType", "auction_type", "type")))
    sld, tld = _split_domain(domain_name)

    return DynadotParsedListing(
        source_listing_id=source_listing_id,
        domain_name=domain_name,
        sld=sld,
        tld=tld,
        auction_type=_map_auction_type(auction_type_text, page_url),
        current_price=_parse_money(_lookup(payload, ("currentPrice", "current_price", "currentBid", "price"))),
        min_next_bid=_parse_money(_lookup(payload, ("minNextBid", "min_next_bid", "nextBid", "minimumBid", "minBid"))),
        bid_count=_parse_int(_lookup(payload, ("bidCount", "bid_count", "bids"))),
        close_time=close_time,
        listing_url=listing_url,
        traffic=_parse_int(_lookup(payload, ("traffic", "visitors", "monthlyVisitors"))),
        revenue=_parse_money(_lookup(payload, ("revenue", "monthlyRevenue"))),
        renewal_price=_parse_money(_lookup(payload, ("renewalPrice", "renewal_price", "renewal"))),
        age_if_available=_parse_int(_lookup(payload, ("age", "domainAge", "ageYears"))),
        source_status=source_status,
        canonical_status=_map_status(source_status, close_time=close_time, captured_at=captured_at),
        raw_payload={
            "extraction_method": "structured_json",
            "record": payload,
            "page_url": page_url,
        },
    )


def _iter_candidate_mappings(payload: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if _mapping_has_listing_shape(payload):
            yield payload
        for value in payload.values():
            yield from _iter_candidate_mappings(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_candidate_mappings(item)


def _mapping_has_listing_shape(payload: Mapping[str, Any]) -> bool:
    domain = _lookup(payload, ("domainName", "domain_name", "domain", "name", "fqdn"))
    if not _looks_like_domain(_clean_domain(domain)):
        return False
    auction_keys = {
        "auctionid",
        "listingid",
        "sourceitemid",
        "currentbid",
        "currentprice",
        "price",
        "minnextbid",
        "bidcount",
        "closetime",
        "endtime",
        "endsat",
        "status",
    }
    normalized_keys = {_normalize_key(key) for key in payload.keys()}
    return bool(normalized_keys.intersection(auction_keys))


def _extract_next_page_cursor(links: Iterable[_Link], scripts: Iterable[str], page_url: str) -> str | None:
    for link in links:
        rel = link.attrs.get("rel", "").lower()
        label = " ".join(
            [
                link.attrs.get("aria-label", ""),
                link.attrs.get("title", ""),
                link.text,
                link.attrs.get("class", ""),
            ]
        ).strip().lower()
        href = link.attrs.get("href")
        if href and ("next" in rel or "next" in label or label in {">", ">>"}):
            return urljoin(page_url, href)

    for script in scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        cursor = _find_next_cursor(payload)
        if isinstance(cursor, str) and cursor.strip():
            return urljoin(page_url, cursor.strip())
        if isinstance(cursor, int):
            return _page_url_with_page_number(page_url, cursor)
    return None


def _find_next_cursor(payload: Any) -> str | int | None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = _normalize_key(str(key))
            if normalized_key in {"nextpageurl", "nexturl", "nextpagecursor", "nextpage"}:
                if isinstance(value, (str, int)):
                    return value
            found = _find_next_cursor(value)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_next_cursor(item)
            if found is not None:
                return found
    return None


def _page_url_with_page_number(page_url: str, page_number: int) -> str:
    parsed = urlparse(page_url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page_number)]
    encoded_pairs = []
    for key, values in query.items():
        for value in values:
            encoded_pairs.append(f"{key}={value}")
    query_text = "&".join(encoded_pairs)
    return parsed._replace(query=query_text).geturl()


def _lookup(payload: Mapping[str, Any], keys: Iterable[str]) -> Any:
    normalized = {_normalize_key(str(key)): value for key, value in payload.items()}
    for key in keys:
        value = normalized.get(_normalize_key(key))
        if value is not None:
            return value
    return None


def _cell_by_alias(field_cells: Mapping[str, _Cell], aliases: Iterable[str]) -> _Cell | None:
    for alias in aliases:
        cell = field_cells.get(_normalize_key(alias))
        if cell is not None:
            return cell
    return None


def _cell_text(field_cells: Mapping[str, _Cell], aliases: Iterable[str]) -> str | None:
    cell = _cell_by_alias(field_cells, aliases)
    return cell.text if cell is not None else None


def _row_source_id(attrs: Mapping[str, str], listing_url: str | None, domain_name: str) -> str:
    for key in ("data-auction-id", "data-listing-id", "data-id", "id"):
        value = attrs.get(key)
        if value:
            return str(value)
    return _source_id_from_url(listing_url) or domain_name


def _source_id_from_url(listing_url: str | None) -> str | None:
    if not listing_url:
        return None
    parsed = urlparse(listing_url)
    query = parse_qs(parsed.query)
    for key in ("id", "auction_id", "listing_id"):
        if key in query and query[key]:
            return query[key][0]
    path_parts = [part for part in parsed.path.split("/") if part]
    return path_parts[-1] if path_parts else None


def _first_listing_url(links: Iterable[_Link], page_url: str) -> str | None:
    for link in links:
        href = link.attrs.get("href")
        if href:
            return urljoin(page_url, href)
    return None


def _absolute_url(value: Any, page_url: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return urljoin(page_url, text)


def _split_domain(domain_name: str) -> tuple[str, str]:
    labels = [label for label in domain_name.lower().strip(".").split(".") if label]
    if len(labels) < 2:
        return domain_name.lower(), ""
    return labels[-2], labels[-1]


def _clean_domain(value: Any) -> str:
    text = _string_or_none(value) or ""
    text = html.unescape(text)
    text = text.strip().lower().strip(".")
    text = re.sub(r"^https?://", "", text)
    text = text.split("/")[0]
    text = text.split("?")[0]
    return text


def _looks_like_domain(value: str) -> bool:
    if not value or "." not in value:
        return False
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", value))


def _parse_money(value: Any, *, default_currency: str = "USD") -> Money | None:
    text = _string_or_none(value)
    if not text or text.lower() in {"-", "n/a", "na", "none"}:
        return None
    currency = default_currency
    if "$" in text or "usd" in text.lower():
        currency = "USD"
    elif "€" in text or "eur" in text.lower():
        currency = "EUR"
    elif "£" in text or "gbp" in text.lower():
        currency = "GBP"

    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    try:
        amount = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    return Money(amount=amount, currency=currency)


def _parse_int(value: Any) -> int | None:
    text = _string_or_none(value)
    if not text or text.lower() in {"-", "n/a", "na", "none"}:
        return None
    compact = text.lower().replace(",", "").strip()
    multiplier = 1
    if compact.endswith("k"):
        multiplier = 1000
        compact = compact[:-1]
    elif compact.endswith("m"):
        multiplier = 1000000
        compact = compact[:-1]
    match = re.search(r"-?\d+(?:\.\d+)?", compact)
    if not match:
        return None
    return int(Decimal(match.group(0)) * multiplier)


def _parse_close_time(value: Any, fallback_text: Any, *, captured_at: datetime) -> datetime | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed
    parsed = _parse_datetime(fallback_text)
    if parsed is not None:
        return parsed
    return _parse_relative_duration(fallback_text, captured_at=captured_at)


def _parse_datetime(value: Any) -> datetime | None:
    text = _string_or_none(value)
    if not text or text.lower() in {"-", "n/a", "na", "none"}:
        return None
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return _ensure_utc(parsed)


def _parse_relative_duration(value: Any, *, captured_at: datetime) -> datetime | None:
    text = (_string_or_none(value) or "").lower()
    if not text:
        return None

    total = timedelta()
    matched = False
    for number, unit in re.findall(r"(\d+)\s*(day|days|d|hour|hours|h|minute|minutes|min|m)", text):
        matched = True
        amount = int(number)
        if unit.startswith("d"):
            total += timedelta(days=amount)
        elif unit.startswith("h"):
            total += timedelta(hours=amount)
        else:
            total += timedelta(minutes=amount)
    if not matched:
        return None
    return captured_at + total


def _map_status(source_status: str | None, *, close_time: datetime | None, captured_at: datetime) -> AuctionStatus:
    status = (source_status or "").strip().lower()
    if status in {"scheduled", "upcoming"}:
        return AuctionStatus.SCHEDULED
    if status in {"open", "active", "live", "running"}:
        if close_time is not None and close_time <= captured_at:
            return AuctionStatus.CLOSED
        return AuctionStatus.OPEN
    if status in {"closing", "ending", "ending soon"}:
        return AuctionStatus.CLOSING
    if status in {"closed", "ended", "complete", "completed"}:
        return AuctionStatus.CLOSED
    if status in {"sold", "won"}:
        return AuctionStatus.SOLD
    if status in {"unsold", "no sale", "not sold"}:
        return AuctionStatus.UNSOLD
    if status in {"cancelled", "canceled"}:
        return AuctionStatus.CANCELLED
    if close_time is not None and close_time > captured_at:
        return AuctionStatus.OPEN
    return AuctionStatus.UNKNOWN


def _map_auction_type(source_type: str | None, page_url: str) -> AuctionType:
    text = " ".join([source_type or "", page_url]).lower()
    if "closeout" in text:
        return AuctionType.CLOSEOUT
    if "backorder" in text:
        return AuctionType.BACKORDER
    if "registry" in text:
        return AuctionType.REGISTRY
    if "user" in text or "private" in text or "market" in text and "auction" not in text:
        return AuctionType.PRIVATE_SELLER
    if "expired" in text or "auction" in text:
        return AuctionType.EXPIRED
    return AuctionType.UNKNOWN


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return None
    text = html.unescape(str(value)).strip()
    return _collapse_text(text) or None


def _collapse_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
