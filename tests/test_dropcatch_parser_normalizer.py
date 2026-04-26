"""Fixture-based tests for DropCatch parsing and normalization."""

from __future__ import annotations

import unittest
from pathlib import Path

from marketplaces.dropcatch.normalizer import DropCatchAuctionNormalizer
from marketplaces.dropcatch.parser import parse_listing_page
from marketplaces.schemas import NormalizeRawItemRequest


FIXTURES = Path(__file__).parent / "fixtures"


class DropCatchParserNormalizerTests(unittest.TestCase):
    def test_parse_listing_page_extracts_required_dropcatch_fields(self) -> None:
        html = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")

        page = parse_listing_page(html, page_url="https://dropcatch.test/auctions")

        self.assertEqual(page.errors, [])
        self.assertEqual(len(page.listings), 2)
        listing = page.listings[0]
        self.assertEqual(listing.source_name, "dropcatch")
        self.assertEqual(listing.source_listing_id, "dc-1001")
        self.assertEqual(listing.domain_name, "example-alpha.com")
        self.assertEqual(listing.sld, "example-alpha")
        self.assertEqual(listing.tld, "com")
        self.assertEqual(listing.auction_type, "Backorder Auction")
        self.assertEqual(listing.current_price.amount, "125.00")
        self.assertEqual(listing.min_next_bid.amount, "130.00")
        self.assertEqual(listing.bid_count, 4)
        self.assertEqual(listing.close_time, "2026-04-24T18:30:00Z")
        self.assertEqual(listing.listing_url, "https://dropcatch.test/auction/example-alpha.com")
        self.assertEqual(listing.traffic, 1234)
        self.assertEqual(listing.revenue.amount, "12.50")
        self.assertEqual(listing.renewal_price.amount, "10.99")
        self.assertEqual(listing.age_if_available, 7)
        self.assertEqual(listing.source_status, "Open")

    def test_parse_listing_page_extracts_embedded_json(self) -> None:
        html = (FIXTURES / "dropcatch_listing_json.html").read_text(encoding="utf-8")

        page = parse_listing_page(html, page_url="https://dropcatch.test/auctions?page=2")

        self.assertEqual(page.errors, [])
        self.assertEqual(len(page.listings), 1)
        listing = page.listings[0]
        self.assertEqual(listing.source_listing_id, "dc-json-2001")
        self.assertEqual(listing.domain_name, "signalvault.com")
        self.assertEqual(listing.close_time, "2026-04-26T20:00:00Z")
        self.assertEqual(listing.current_price.amount, "250.00")
        self.assertEqual(listing.min_next_bid.amount, "260.00")

    def test_normalizer_maps_dropcatch_payload_to_canonical_schema(self) -> None:
        html = (FIXTURES / "dropcatch_listing_page_1.html").read_text(encoding="utf-8")
        listing = parse_listing_page(html, page_url="https://dropcatch.test/auctions").listings[0]
        normalizer = DropCatchAuctionNormalizer()

        response = normalizer.normalize_raw_item(
            NormalizeRawItemRequest(
                raw_auction_item_id="raw-1",
                marketplace_code="dropcatch",
                raw_payload_json=listing.to_raw_payload_json(),
                source_url=listing.listing_url,
                captured_at="2026-04-23T12:00:00Z",
            )
        )

        self.assertEqual(response.errors, [])
        self.assertEqual(response.domain.fqdn, "example-alpha.com")
        self.assertEqual(response.domain.sld, "example-alpha")
        self.assertEqual(response.domain.tld, "com")
        self.assertEqual(response.auction.marketplace_code, "dropcatch")
        self.assertEqual(response.auction.source_item_id, "dc-1001")
        self.assertEqual(response.auction.auction_type, "backorder")
        self.assertEqual(response.auction.status, "open")
        self.assertEqual(response.auction.ends_at, "2026-04-24T18:30:00Z")
        self.assertEqual(response.auction.current_bid.amount, "125.00")
        self.assertEqual(response.auction.min_bid.amount, "130.00")
        self.assertEqual(response.auction.bid_count, 4)
        self.assertEqual(response.auction.normalized_payload_json["traffic"], 1234)
        self.assertEqual(response.snapshot.captured_at, "2026-04-23T12:00:00Z")
        self.assertEqual(response.snapshot.status, "open")
        self.assertEqual(response.evidence_refs[0].type, "raw_auction_item")
        self.assertEqual(response.evidence_refs[0].id, "raw-1")

    def test_normalizer_returns_refusal_error_for_invalid_domain(self) -> None:
        normalizer = DropCatchAuctionNormalizer()

        response = normalizer.normalize_raw_item(
            NormalizeRawItemRequest(
                raw_auction_item_id="raw-2",
                marketplace_code="dropcatch",
                raw_payload_json={"domain_name": "not a domain", "source_listing_id": "bad-1"},
                source_url=None,
                captured_at="2026-04-23T12:00:00Z",
            )
        )

        self.assertEqual(response.domain, None)
        self.assertEqual(response.auction, None)
        self.assertEqual(response.errors[0].code, "domain_invalid")


if __name__ == "__main__":
    unittest.main()
