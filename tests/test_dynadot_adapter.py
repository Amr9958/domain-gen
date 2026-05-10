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
from domain_intel.marketplaces.dynadot import (
    DynadotAuctionAdapter,
    DynadotAuctionAdapterConfig,
    DynadotAuctionApiConfig,
    parse_dynadot_listing_page,
)
from domain_intel.marketplaces.run_logging import InMemoryScrapeRunLogger
from domain_intel.marketplaces.schemas import FetchedPage, FetchAuctionItemsRequest, FetchAuctionItemsResponse
from domain_intel.normalization import DynadotAuctionNormalizer, NormalizeRawItemRequest


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


class _FailingFetcher:
    def __init__(self) -> None:
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
        raise AssertionError("Dynadot API mode must not call the scraping fetcher")


class _FakeDynadotApiClient:
    def __init__(self, response: FetchAuctionItemsResponse) -> None:
        self.response = response
        self.calls: list[tuple[FetchAuctionItemsRequest, DynadotAuctionApiConfig]] = []

    def fetch_auction_items(
        self,
        request: FetchAuctionItemsRequest,
        *,
        config: DynadotAuctionApiConfig,
    ) -> FetchAuctionItemsResponse:
        self.calls.append((request, config))
        return self.response


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
    def test_default_production_scraping_fallback_is_disabled(self) -> None:
        logger = InMemoryScrapeRunLogger()
        adapter = DynadotAuctionAdapter(run_logger=logger)

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DYNADOT,
                ingest_run_id="approval-gate",
                limit=100,
            )
        )

        self.assertEqual(response.items, [])
        self.assertEqual(response.errors[0].code, "source_not_approved")
        self.assertIn("API-first", response.errors[0].message)
        self.assertEqual(response.errors[0].details["production_scraping_fallback_enabled"], False)
        self.assertEqual(logger.metrics.pages_attempted, 0)

    def test_injected_fetcher_does_not_bypass_disabled_scraping_fallback(self) -> None:
        fetcher = _FailingFetcher()
        adapter = DynadotAuctionAdapter(fetcher=fetcher)

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DYNADOT,
                ingest_run_id="injected-fetcher-gate",
                limit=100,
            )
        )

        self.assertEqual(response.items, [])
        self.assertEqual(response.errors[0].code, "source_not_approved")
        self.assertEqual(fetcher.calls, [])

    def test_api_enabled_without_client_returns_local_unavailable_error(self) -> None:
        logger = InMemoryScrapeRunLogger()
        adapter = DynadotAuctionAdapter(
            config=DynadotAuctionAdapterConfig(api=DynadotAuctionApiConfig(enabled=True)),
            run_logger=logger,
        )

        response = adapter.fetch_auction_items(
            FetchAuctionItemsRequest(
                marketplace_code=MarketplaceCode.DYNADOT,
                ingest_run_id="api-skeleton-missing-client",
                limit=100,
            )
        )

        self.assertEqual(response.items, [])
        self.assertEqual(response.errors[0].code, "api_client_unavailable")
        self.assertEqual(response.errors[0].details["api_enabled"], True)
        self.assertEqual(response.errors[0].details["api_base_url_configured"], False)
        self.assertEqual(response.errors[0].details["credential_env_var"], "DYNADOT_API_KEY")
        self.assertEqual(logger.metrics.pages_attempted, 0)

    def test_api_enabled_uses_api_client_without_scraping_fetcher(self) -> None:
        api_response = FetchAuctionItemsResponse(items=[], next_page_cursor="api-page-2", errors=[])
        api_client = _FakeDynadotApiClient(api_response)
        fetcher = _FailingFetcher()
        adapter = DynadotAuctionAdapter(
            config=DynadotAuctionAdapterConfig(
                api=DynadotAuctionApiConfig(enabled=True, base_url="https://api.example.invalid/dynadot")
            ),
            api_client=api_client,
            fetcher=fetcher,
        )
        request = FetchAuctionItemsRequest(
            marketplace_code=MarketplaceCode.DYNADOT,
            ingest_run_id="api-skeleton-client",
            page_cursor="api-page-1",
            limit=100,
        )

        response = adapter.fetch_auction_items(request)

        self.assertEqual(response, api_response)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(len(api_client.calls), 1)
        self.assertIs(api_client.calls[0][0], request)
        self.assertTrue(api_client.calls[0][1].enabled)

    def test_fetch_all_handles_pagination_hashes_and_duplicate_listing_hooks(self) -> None:
        fetcher = _FakeFetcher(
            {
                PAGE_1_URL: _read_fixture("expired_auction_page_1.html"),
                PAGE_2_URL: _read_fixture("expired_auction_page_2.html"),
            }
        )
        logger = InMemoryScrapeRunLogger()
        adapter = DynadotAuctionAdapter(
            fetcher=fetcher,
            run_logger=logger,
            config=DynadotAuctionAdapterConfig(fixture_fetching_enabled=True),
        )

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
        self.assertEqual(first_item["raw_payload_json"]["extraction_method"], "html_table")
        self.assertEqual(first_item["raw_payload_json"]["page_url"], PAGE_1_URL)
        self.assertIn("cells", first_item["raw_payload_json"])

    def test_normalizer_maps_raw_observation_to_canonical_schema(self) -> None:
        parsed = parse_dynadot_listing_page(
            _read_fixture("expired_auction_page_1.html"),
            page_url=PAGE_1_URL,
            captured_at=CAPTURED_AT,
        )
        normalizer = DynadotAuctionNormalizer()

        normalized = normalizer.normalize_raw_item(
            NormalizeRawItemRequest(
                raw_auction_item_id="raw-dynadot-1",
                marketplace_code=MarketplaceCode.DYNADOT,
                source_item_id=parsed.listings[0].source_listing_id,
                raw_payload_json=parsed.listings[0].raw_payload,
                source_url=parsed.listings[0].listing_url,
                captured_at=CAPTURED_AT,
            )
        )

        self.assertEqual(normalized.errors, [])
        self.assertEqual(normalized.domain.fqdn, "alpha-investor.test")
        self.assertEqual(normalized.auction.marketplace_code.value, "dynadot")
        self.assertEqual(normalized.auction.source_item_id, "dynadot-fixture-1001")
        self.assertEqual(normalized.auction.status.value, "open")
        self.assertEqual(normalized.auction.current_bid.to_api_dict(), {"amount": "120.00", "currency": "USD"})
        self.assertEqual(normalized.snapshot.status.value, "open")
        self.assertEqual(normalized.evidence_refs[0].id, "raw-dynadot-1")


if __name__ == "__main__":
    unittest.main()
