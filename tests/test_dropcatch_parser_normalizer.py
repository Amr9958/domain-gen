"""Fixture-based tests for DropCatch parsing and normalization."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from domain_intel.core.enums import MarketplaceCode
from domain_intel.marketplaces.dropcatch.parser import parse_dropcatch_listing_page
from domain_intel.normalization import DropCatchAuctionNormalizer, NormalizeRawItemRequest


FIXTURES = Path(__file__).parent / "fixtures"


class DropCatchParserNormalizerTests(unittest.TestCase):
    def test_parse_listing_page_extracts_required_dropcatch_fields(self) -> None:
        html = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")

        page = parse_dropcatch_listing_page(html, page_url="https://dropcatch.test/auctions")

        self.assertEqual(page.errors, [])
        self.assertEqual(len(page.listings), 2)
        listing = page.listings[0]
        self.assertEqual(listing.source_name, "dropcatch")
        self.assertEqual(listing.source_listing_id, "dc-1001")
        self.assertEqual(listing.domain_name, "example-alpha.com")
        self.assertEqual(listing.sld, "example-alpha")
        self.assertEqual(listing.tld, "com")
        self.assertEqual(listing.auction_type, "Backorder Auction")
        self.assertEqual(listing.current_price.to_api_dict(), {"amount": "125.00", "currency": "USD"})
        self.assertEqual(listing.min_next_bid.to_api_dict(), {"amount": "130.00", "currency": "USD"})
        self.assertEqual(listing.bid_count, 4)
        self.assertEqual(listing.close_time.isoformat().replace("+00:00", "Z"), "2026-04-24T18:30:00Z")
        self.assertEqual(listing.listing_url, "https://dropcatch.test/auction/example-alpha.com")
        self.assertEqual(listing.traffic, 1234)
        self.assertEqual(listing.revenue.to_api_dict(), {"amount": "12.50", "currency": "USD"})
        self.assertEqual(listing.renewal_price.to_api_dict(), {"amount": "10.99", "currency": "USD"})
        self.assertEqual(listing.age_if_available, 7)
        self.assertEqual(listing.source_status, "Open")

    def test_parse_listing_page_extracts_embedded_json(self) -> None:
        html = (FIXTURES / "dropcatch_listing_json.html").read_text(encoding="utf-8")

        page = parse_dropcatch_listing_page(html, page_url="https://dropcatch.test/auctions?page=2")

        self.assertEqual(page.errors, [])
        self.assertEqual(len(page.listings), 1)
        listing = page.listings[0]
        self.assertEqual(listing.source_listing_id, "dc-json-2001")
        self.assertEqual(listing.domain_name, "signalvault.com")
        self.assertEqual(listing.close_time.isoformat().replace("+00:00", "Z"), "2026-04-26T20:00:00Z")
        self.assertEqual(listing.current_price.to_api_dict(), {"amount": "250.00", "currency": "USD"})
        self.assertEqual(listing.min_next_bid.to_api_dict(), {"amount": "260.00", "currency": "USD"})

    def test_normalizer_maps_dropcatch_payload_to_canonical_schema(self) -> None:
        html = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")
        listing = parse_dropcatch_listing_page(html, page_url="https://dropcatch.test/auctions").listings[0]
        normalizer = DropCatchAuctionNormalizer()
        captured_at = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)

        response = normalizer.normalize_raw_item(
            NormalizeRawItemRequest(
                raw_auction_item_id="raw-1",
                marketplace_code=MarketplaceCode.DROPCATCH,
                source_item_id=listing.source_listing_id,
                raw_payload_json=listing.raw_payload,
                source_url=listing.listing_url,
                captured_at=captured_at,
            )
        )

        self.assertEqual(response.errors, [])
        self.assertEqual(response.domain.fqdn, "example-alpha.com")
        self.assertEqual(response.domain.sld, "example-alpha")
        self.assertEqual(response.domain.tld, "com")
        self.assertEqual(response.auction.marketplace_code.value, "dropcatch")
        self.assertEqual(response.auction.source_item_id, "dc-1001")
        self.assertEqual(response.auction.auction_type.value, "backorder")
        self.assertEqual(response.auction.status.value, "open")
        self.assertEqual(response.auction.ends_at.isoformat().replace("+00:00", "Z"), "2026-04-24T18:30:00Z")
        self.assertEqual(response.auction.current_bid.to_api_dict(), {"amount": "125.00", "currency": "USD"})
        self.assertEqual(response.auction.min_bid.to_api_dict(), {"amount": "130.00", "currency": "USD"})
        self.assertEqual(response.auction.bid_count, 4)
        self.assertEqual(response.auction.normalized_payload_json["traffic"], 1234)
        self.assertEqual(response.snapshot.captured_at.isoformat().replace("+00:00", "Z"), "2026-04-23T12:00:00Z")
        self.assertEqual(response.snapshot.status.value, "open")
        self.assertEqual(response.evidence_refs[0].type, "raw_auction_item")
        self.assertEqual(response.evidence_refs[0].id, "raw-1")

    def test_normalizer_returns_refusal_error_for_invalid_domain(self) -> None:
        normalizer = DropCatchAuctionNormalizer()

        response = normalizer.normalize_raw_item(
            NormalizeRawItemRequest(
                raw_auction_item_id="raw-2",
                marketplace_code=MarketplaceCode.DROPCATCH,
                source_item_id="bad-1",
                raw_payload_json={"extraction_method": "structured_json", "record": {"domain_name": "not a domain"}},
                source_url=None,
                captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc),
            )
        )

        self.assertEqual(response.domain, None)
        self.assertEqual(response.auction, None)
        self.assertEqual(response.errors[0].code, "normalization_failed")


if __name__ == "__main__":
    unittest.main()
