"""Tests for the DropCatch marketplace adapter."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from domain_intel.core.enums import MarketplaceCode
from domain_intel.marketplaces.dropcatch import DropCatchAuctionAdapter, DropCatchAuctionAdapterConfig
from domain_intel.marketplaces.run_logging import InMemoryScrapeRunLogger
from domain_intel.marketplaces.schemas import FetchedPage, FetchAuctionItemsRequest


FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested_urls: list[str] = []

    def fetch(self, url: str, *, headers=None, timeout_seconds=None) -> FetchedPage:
        _ = (headers, timeout_seconds)
        self.requested_urls.append(url)
        return FetchedPage(url=url, status_code=200, text=self.pages[url], headers={})


class _FlakyFetcher:
    def __init__(self, page: str) -> None:
        self.page = page
        self.calls = 0

    def fetch(self, url: str, *, headers=None, timeout_seconds=None) -> FetchedPage:
        _ = (headers, timeout_seconds)
        self.calls += 1
        if self.calls == 1:
            from domain_intel.marketplaces.base import PageFetchError

            raise PageFetchError("HTTP 503 while fetching marketplace page", code="http_error", status_code=503, retryable=True)
        return FetchedPage(url=url, status_code=200, text=self.page, headers={})


class DropCatchAdapterTests(unittest.TestCase):
    def test_fetch_auction_items_maps_fixture_to_raw_contract(self) -> None:
        page_url = "https://dropcatch.test/auctions"
        html = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")
        logger = InMemoryScrapeRunLogger()
        adapter = DropCatchAuctionAdapter(
            config=DropCatchAuctionAdapterConfig(default_listing_url=page_url),
            fetcher=_FixtureFetcher({page_url: html}),
            run_logger=logger,
        )

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DROPCATCH,
                ingest_run_id="run-1",
                limit=10,
            )
        )

        self.assertEqual(response.errors, [])
        self.assertEqual(len(response.items), 2)
        self.assertEqual(response.next_page_cursor, "https://dropcatch.test/auctions?page=2")
        first = response.items[0]
        self.assertEqual(first.marketplace_code.value, "dropcatch")
        self.assertEqual(first.source_item_id, "dc-1001")
        self.assertEqual(first.source_url, "https://dropcatch.test/auction/example-alpha.com")
        self.assertTrue(first.raw_payload_hash.startswith("sha256:"))
        self.assertEqual(first.raw_payload_json["extraction_method"], "html_table")
        self.assertEqual(first.raw_payload_json["page_url"], page_url)
        self.assertEqual(first.raw_payload_json["cells"][0], "Example-Alpha.com")
        self.assertEqual(logger.metrics.pages_attempted, 1)
        self.assertEqual(logger.metrics.items_emitted, 2)

    def test_fetch_all_auction_items_traverses_next_page_cursor(self) -> None:
        page_1_url = "https://dropcatch.test/auctions"
        page_2_url = "https://dropcatch.test/auctions?page=2"
        page_1 = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")
        page_2 = (FIXTURES / "dropcatch_listing_json.html").read_text(encoding="utf-8")
        fetcher = _FixtureFetcher({page_1_url: page_1, page_2_url: page_2})
        adapter = DropCatchAuctionAdapter(
            config=DropCatchAuctionAdapterConfig(default_listing_url=page_1_url),
            fetcher=fetcher,
        )

        response = adapter.fetch_all_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DROPCATCH,
                ingest_run_id="run-2",
                limit=10,
            ),
            max_pages=3,
        )

        self.assertEqual(response.errors, [])
        self.assertEqual([item.source_item_id for item in response.items], ["dc-1001", "dc-1002", "dc-json-2001"])
        self.assertEqual(fetcher.requested_urls, [page_1_url, page_2_url])

    def test_fetch_auction_items_surfaces_structured_fetch_errors(self) -> None:
        page_url = "https://dropcatch.test/auctions"
        html = (FIXTURES / "dropcatch_listing_json.html").read_text(encoding="utf-8")
        fetcher = _FlakyFetcher(html)
        adapter = DropCatchAuctionAdapter(
            config=DropCatchAuctionAdapterConfig(default_listing_url=page_url),
            fetcher=fetcher,
        )

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DROPCATCH,
                ingest_run_id="run-3",
                limit=10,
            )
        )

        self.assertEqual(len(response.items), 0)
        self.assertEqual(response.errors[0].code, "http_error")
        self.assertEqual(fetcher.calls, 1)


if __name__ == "__main__":
    unittest.main()
