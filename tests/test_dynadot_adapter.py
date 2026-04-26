"""Tests for Dynadot marketplace parsing and adapter behavior."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from domain_intel.core.enums import MarketplaceCode
from domain_intel.marketplaces.base import PageFetchError
from domain_intel.marketplaces.dynadot import DynadotAuctionAdapter, parse_dynadot_listing_page
from domain_intel.marketplaces.run_logging import InMemoryScrapeRunLogger
from domain_intel.marketplaces.schemas import FetchedPage, FetchAuctionItemsRequest


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dynadot"
PAGE_1_URL = "https://www.dynadot.com/market/auction?show=100"
PAGE_2_URL = "https://www.dynadot.com/market/auction?page=2&show=100"
CAPTURED_AT = datetime(2026, 4, 23, 16, 0, tzinfo=timezone.utc)


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class _FakeFetcher:
    def __init__(self, pages: Mapping[str, str]) -> None:
        self.pages = dict(pages)
        self.calls: list[str] = []

    def fetch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> FetchedPage:
        _ = headers, timeout_seconds
        self.calls.append(url)
        page = self.pages.get(url)
        if page is None:
            raise PageFetchError(f"No fixture registered for {url}", code="fixture_missing")
        return FetchedPage(url=url, status_code=200, text=page, headers={})


class DynadotParserTests(unittest.TestCase):
    def test_table_fixture_maps_to_normalized_listing_fields(self) -> None:
        parsed = parse_dynadot_listing_page(
            _read_fixture("expired_auction_page_1.html"),
            page_url=PAGE_1_URL,
            captured_at=CAPTURED_AT,
        )

        normalized = [listing.to_normalized().to_api_dict() for listing in parsed.listings]
        expected = json.loads((FIXTURE_DIR / "normalized_page_1.json").read_text(encoding="utf-8"))

        self.assertEqual(len(normalized), 2)
        self.assertEqual(parsed.next_page_cursor, PAGE_2_URL)
        for index, expected_listing in enumerate(expected):
            for key, expected_value in expected_listing.items():
                if key == "raw_payload":
                    self.assertEqual(normalized[index]["raw_payload"]["extraction_method"], expected_value["extraction_method"])
                    self.assertEqual(normalized[index]["raw_payload"]["page_url"], expected_value["page_url"])
                    continue
                self.assertEqual(normalized[index][key], expected_value)

    def test_structured_json_fixture_is_parsed_without_table_markup(self) -> None:
        parsed = parse_dynadot_listing_page(
            _read_fixture("structured_auction_page.html"),
            page_url=PAGE_1_URL,
            captured_at=CAPTURED_AT,
        )

        self.assertEqual(len(parsed.listings), 1)
        listing = parsed.listings[0].to_normalized().to_api_dict()

        self.assertEqual(listing["source_listing_id"], "dynadot-fixture-json-2001")
        self.assertEqual(listing["domain_name"], "jsonsignal.test")
        self.assertEqual(listing["current_price"], {"amount": "88.00", "currency": "USD"})
        self.assertEqual(listing["min_next_bid"], {"amount": "93.00", "currency": "USD"})
        self.assertEqual(listing["canonical_status"], "open")
        self.assertEqual(listing["raw_payload"]["extraction_method"], "structured_json")


class DynadotAdapterTests(unittest.TestCase):
    def test_fetch_all_handles_pagination_hashes_and_duplicate_listing_hooks(self) -> None:
        fetcher = _FakeFetcher(
            {
                PAGE_1_URL: _read_fixture("expired_auction_page_1.html"),
                PAGE_2_URL: _read_fixture("expired_auction_page_2.html"),
            }
        )
        logger = InMemoryScrapeRunLogger()
        adapter = DynadotAuctionAdapter(fetcher=fetcher, run_logger=logger)

        response = adapter.fetch_all_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DYNADOT,
                ingest_run_id="fixture-run-1",
                limit=100,
            ),
            max_pages=2,
        )

        self.assertEqual(fetcher.calls, [PAGE_1_URL, PAGE_2_URL])
        self.assertEqual(response.errors, [])
        self.assertIsNone(response.next_page_cursor)
        self.assertEqual(len(response.items), 3)
        self.assertEqual(logger.metrics.pages_attempted, 2)
        self.assertEqual(logger.metrics.pages_succeeded, 2)
        self.assertEqual(logger.metrics.items_seen, 4)
        self.assertEqual(logger.metrics.items_emitted, 3)
        self.assertEqual(logger.metrics.duplicate_items, 1)

        first_item = response.items[0].to_api_dict()
        self.assertEqual(first_item["marketplace_code"], "dynadot")
        self.assertEqual(first_item["source_item_id"], "dynadot-fixture-1001")
        self.assertTrue(first_item["raw_payload_hash"].startswith("sha256:"))
        self.assertEqual(first_item["raw_payload_json"]["source_name"], "dynadot")
        self.assertEqual(first_item["raw_payload_json"]["auction_type"], "expired")
        self.assertEqual(first_item["raw_payload_json"]["adapter_metadata"]["parser_version"], "dynadot-parser-v1")


if __name__ == "__main__":
    unittest.main()
