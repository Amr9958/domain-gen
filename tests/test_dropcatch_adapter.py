"""Tests for the DropCatch marketplace adapter."""

from __future__ import annotations

import unittest
from pathlib import Path
from urllib.error import HTTPError

from marketplaces.base import RetryPolicy
from marketplaces.dropcatch import DropCatchAdapter
from marketplaces.schemas import FetchAuctionItemsRequest


FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested_urls: list[str] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> str:
        _ = (headers, timeout)
        self.requested_urls.append(url)
        return self.pages[url]


class _FlakyHttpClient:
    def __init__(self, page: str) -> None:
        self.page = page
        self.calls = 0

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> str:
        _ = (url, headers, timeout)
        self.calls += 1
        if self.calls == 1:
            raise HTTPError(url, 503, "temporary", hdrs=None, fp=None)
        return self.page


class _MemoryScrapeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, int | None]] = []

    def page_started(self, *, ingest_run_id: str, marketplace_code: str, page_url: str) -> None:
        _ = (ingest_run_id, marketplace_code)
        self.events.append(("started", page_url, None))

    def page_completed(
        self,
        *,
        ingest_run_id: str,
        marketplace_code: str,
        page_url: str,
        item_count: int,
        next_page_cursor: str | None,
    ) -> None:
        _ = (ingest_run_id, marketplace_code, next_page_cursor)
        self.events.append(("completed", page_url, item_count))

    def page_failed(
        self,
        *,
        ingest_run_id: str,
        marketplace_code: str,
        page_url: str,
        error: object,
        retry_count: int,
    ) -> None:
        _ = (ingest_run_id, marketplace_code, error)
        self.events.append(("failed", page_url, retry_count))


class DropCatchAdapterTests(unittest.TestCase):
    def test_fetch_auction_items_maps_fixture_to_raw_contract(self) -> None:
        page_url = "https://dropcatch.test/auctions"
        html = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")
        logger = _MemoryScrapeLogger()
        adapter = DropCatchAdapter(
            listing_url=page_url,
            http_client=_FixtureHttpClient({page_url: html}),
            scrape_logger=logger,
        )

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code="dropcatch",
                ingest_run_id="run-1",
                limit=10,
            )
        )

        self.assertEqual(response.errors, [])
        self.assertEqual(len(response.items), 2)
        self.assertEqual(response.next_page_cursor, "https://dropcatch.test/auctions?page=2")
        first = response.items[0]
        self.assertEqual(first.marketplace_code, "dropcatch")
        self.assertEqual(first.source_item_id, "dc-1001")
        self.assertEqual(first.source_url, "https://dropcatch.test/auction/example-alpha.com")
        self.assertTrue(first.raw_payload_hash.startswith("sha256:"))
        self.assertEqual(first.raw_payload_json["domain_name"], "example-alpha.com")
        self.assertEqual(first.raw_payload_json["current_price"], {"amount": "125.00", "currency": "USD"})
        self.assertEqual(first.raw_payload_json["min_next_bid"], {"amount": "130.00", "currency": "USD"})
        self.assertEqual(first.raw_payload_json["bid_count"], 4)
        self.assertEqual(first.raw_payload_json["traffic"], 1234)
        self.assertEqual(first.raw_payload_json["revenue"], {"amount": "12.50", "currency": "USD"})
        self.assertEqual(first.raw_payload_json["renewal_price"], {"amount": "10.99", "currency": "USD"})
        self.assertEqual(first.raw_payload_json["age_if_available"], 7)
        self.assertIn(first.dedupe_key, response.dedupe_keys())
        self.assertEqual(logger.events[0], ("started", page_url, None))
        self.assertEqual(logger.events[-1], ("completed", page_url, 2))

    def test_fetch_all_auction_items_traverses_next_page_cursor(self) -> None:
        page_1_url = "https://dropcatch.test/auctions"
        page_2_url = "https://dropcatch.test/auctions?page=2"
        page_1 = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")
        page_2 = (FIXTURES / "dropcatch_listing_json.html").read_text(encoding="utf-8")
        http_client = _FixtureHttpClient({page_1_url: page_1, page_2_url: page_2})
        adapter = DropCatchAdapter(listing_url=page_1_url, http_client=http_client)

        response = adapter.fetch_all_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code="dropcatch",
                ingest_run_id="run-2",
                limit=10,
            ),
            max_pages=3,
        )

        self.assertEqual(response.errors, [])
        self.assertEqual([item.source_item_id for item in response.items], ["dc-1001", "dc-1002", "dc-json-2001"])
        self.assertEqual(http_client.requested_urls, [page_1_url, page_2_url])

    def test_fetch_auction_items_retries_transient_http_errors(self) -> None:
        page_url = "https://dropcatch.test/auctions"
        html = (FIXTURES / "dropcatch_listing_json.html").read_text(encoding="utf-8")
        http_client = _FlakyHttpClient(html)
        adapter = DropCatchAdapter(
            listing_url=page_url,
            http_client=http_client,
            retry_policy=RetryPolicy(attempts=2, initial_delay_seconds=0.0),
        )

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code="dropcatch",
                ingest_run_id="run-3",
                limit=10,
            )
        )

        self.assertEqual(response.errors, [])
        self.assertEqual(len(response.items), 1)
        self.assertEqual(http_client.calls, 2)


if __name__ == "__main__":
    unittest.main()
