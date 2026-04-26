"""DropCatch source adapter for raw auction ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.logging import get_logger
from marketplaces.base import (
    HttpClient,
    NoopScrapeRunLogger,
    RetryPolicy,
    ScrapeRunLogger,
    UrllibHttpClient,
    fetch_with_retries,
)
from marketplaces.dropcatch.parser import MARKETPLACE_CODE, PARSER_VERSION, parse_listing_page
from marketplaces.schemas import AdapterError, FetchAuctionItemsRequest, FetchAuctionItemsResponse, RawAuctionItem


logger = get_logger("marketplaces.dropcatch.adapter")
ADAPTER_VERSION = "dropcatch-adapter-v1"


@dataclass
class DropCatchAdapter:
    """Fetch DropCatch auction listing pages and emit raw source observations.

    The listing URL is intentionally injectable because production source access
    and approved endpoint selection are still a human decision in requirements.md.
    """

    listing_url: str | None = None
    http_client: HttpClient = field(default_factory=UrllibHttpClient)
    scrape_logger: ScrapeRunLogger = field(default_factory=NoopScrapeRunLogger)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: int = 20
    user_agent: str = "domain-intelligence-saas/0.1 (+operator-configured)"

    def fetch_auction_items(self, request: FetchAuctionItemsRequest) -> FetchAuctionItemsResponse:
        """Fetch one DropCatch listing page and return raw auction items."""
        if request.marketplace_code != MARKETPLACE_CODE:
            return FetchAuctionItemsResponse(
                items=[],
                errors=[
                    AdapterError(
                        code="schema_contract_mismatch",
                        message="DropCatch adapter received a non-DropCatch marketplace code.",
                        details={"marketplace_code": request.marketplace_code},
                    )
                ],
            )

        page_url = request.page_cursor or self.listing_url
        if not page_url:
            return FetchAuctionItemsResponse(
                items=[],
                errors=[
                    AdapterError(
                        code="source_unavailable",
                        message="DropCatch listing URL is not configured for this adapter instance.",
                        details={"marketplace_code": MARKETPLACE_CODE},
                    )
                ],
            )

        self.scrape_logger.page_started(
            ingest_run_id=request.ingest_run_id,
            marketplace_code=MARKETPLACE_CODE,
            page_url=page_url,
        )
        html, fetch_error, retry_count = fetch_with_retries(
            client=self.http_client,
            url=page_url,
            headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
            timeout=self.timeout_seconds,
            retry_policy=self.retry_policy,
        )
        if fetch_error or html is None:
            error = fetch_error or AdapterError(
                code="source_unavailable",
                message="DropCatch page fetch returned no content.",
                details={"url": page_url},
            )
            self.scrape_logger.page_failed(
                ingest_run_id=request.ingest_run_id,
                marketplace_code=MARKETPLACE_CODE,
                page_url=page_url,
                error=error,
                retry_count=retry_count,
            )
            return FetchAuctionItemsResponse(items=[], errors=[error])

        captured_at = _now_utc_iso()
        page = parse_listing_page(html, page_url=page_url)
        raw_items: list[RawAuctionItem] = []
        seen_keys: set[tuple[str, str, str]] = set()

        for listing in page.listings[: max(0, request.limit)]:
            raw_payload_json = listing.to_raw_payload_json()
            raw_item = RawAuctionItem.from_payload(
                marketplace_code=MARKETPLACE_CODE,
                source_item_id=listing.source_listing_id,
                source_url=listing.listing_url,
                captured_at=captured_at,
                raw_payload_json=raw_payload_json,
                adapter_version=ADAPTER_VERSION,
                parser_version=PARSER_VERSION,
            )
            if raw_item.dedupe_key in seen_keys:
                continue
            seen_keys.add(raw_item.dedupe_key)
            raw_items.append(raw_item)

        self.scrape_logger.page_completed(
            ingest_run_id=request.ingest_run_id,
            marketplace_code=MARKETPLACE_CODE,
            page_url=page_url,
            item_count=len(raw_items),
            next_page_cursor=page.next_page_cursor,
        )
        logger.info(
            "Fetched %s DropCatch raw auction items for ingest_run_id=%s.",
            len(raw_items),
            request.ingest_run_id,
        )
        return FetchAuctionItemsResponse(
            items=raw_items,
            next_page_cursor=page.next_page_cursor,
            errors=page.errors,
        )

    def fetch_all_auction_items(
        self,
        request: FetchAuctionItemsRequest,
        *,
        max_pages: int = 5,
    ) -> FetchAuctionItemsResponse:
        """Traverse listing pages using opaque next-page cursors from the parser."""
        items: list[RawAuctionItem] = []
        errors: list[AdapterError] = []
        cursor = request.page_cursor
        seen_keys: set[tuple[str, str, str]] = set()

        for _ in range(max(1, max_pages)):
            page_request = FetchAuctionItemsRequest(
                marketplace_code=request.marketplace_code,
                ingest_run_id=request.ingest_run_id,
                page_cursor=cursor,
                limit=request.limit,
                started_after=request.started_after,
            )
            response = self.fetch_auction_items(page_request)
            errors.extend(response.errors)
            for item in response.items:
                if item.dedupe_key in seen_keys:
                    continue
                seen_keys.add(item.dedupe_key)
                items.append(item)
            cursor = response.next_page_cursor
            if not cursor or errors:
                break

        return FetchAuctionItemsResponse(items=items, next_page_cursor=cursor, errors=errors)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
