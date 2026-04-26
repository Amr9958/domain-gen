"""DropCatch auction adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from domain_intel.core.enums import MarketplaceCode
from domain_intel.marketplaces.base import (
    DeduplicationKey,
    DeduplicationStore,
    InMemoryDeduplicationStore,
    PageFetchError,
    PageFetcher,
)
from domain_intel.marketplaces.http import RetryPolicy, SafeHttpConfig, SafeHttpPageFetcher
from domain_intel.marketplaces.run_logging import NoopScrapeRunLogger, ScrapeRunLogger, ScrapeRunMetrics
from domain_intel.marketplaces.schemas import (
    FetchAuctionItemsRequest,
    FetchAuctionItemsResponse,
    ModuleError,
    RawAuctionItemObservation,
    stable_payload_hash,
)
from domain_intel.marketplaces.dropcatch.parser import PARSER_VERSION, SOURCE_NAME, parse_dropcatch_listing_page


ADAPTER_VERSION = "dropcatch-adapter-v1"


@dataclass(frozen=True)
class DropCatchAuctionAdapterConfig:
    """Configuration for DropCatch listing ingestion."""

    default_listing_url: str | None = None
    request_timeout_seconds: float = 20.0
    user_agent: str = "DomainIntelBot/0.1 (+https://example.invalid/contact)"
    min_delay_between_requests_seconds: float = 1.5
    max_pages_per_run: int = 10
    respect_robots_txt: bool = True
    allowed_hosts: tuple[str, ...] = ("www.dropcatch.com", "dropcatch.com", "dropcatch.test")
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


class DropCatchAuctionAdapter:
    """Fetch and parse DropCatch listing pages into raw auction observations."""

    adapter_version = ADAPTER_VERSION
    parser_version = PARSER_VERSION
    source_name = SOURCE_NAME

    def __init__(
        self,
        *,
        fetcher: PageFetcher | None = None,
        run_logger: ScrapeRunLogger | None = None,
        dedup_store: DeduplicationStore | None = None,
        config: DropCatchAuctionAdapterConfig | None = None,
    ) -> None:
        self.config = config or DropCatchAuctionAdapterConfig()
        self.fetcher = fetcher or SafeHttpPageFetcher(
            SafeHttpConfig(
                user_agent=self.config.user_agent,
                timeout_seconds=self.config.request_timeout_seconds,
                allowed_hosts=self.config.allowed_hosts,
                min_delay_between_requests_seconds=self.config.min_delay_between_requests_seconds,
                respect_robots_txt=self.config.respect_robots_txt,
                retry_policy=self.config.retry_policy,
            )
        )
        self.run_logger = run_logger or NoopScrapeRunLogger()
        self.dedup_store = dedup_store or InMemoryDeduplicationStore()

    def fetch_auction_items(self, request: FetchAuctionItemsRequest) -> FetchAuctionItemsResponse:
        """Fetch one DropCatch listing page and return raw observations."""

        started_at = _utc_now()
        metrics = ScrapeRunMetrics(started_at=started_at)
        self.run_logger.run_started(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            adapter_version=self.adapter_version,
            parser_version=self.parser_version,
            started_at=started_at,
        )
        response = self._fetch_page(request, metrics=metrics)
        completed_at = _utc_now()
        metrics.completed_at = completed_at
        self.run_logger.run_completed(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            status="failed" if response.errors and not response.items else "completed",
            metrics=metrics.to_dict(),
            completed_at=completed_at,
        )
        return response

    def fetch_all_auction_items(
        self,
        request: FetchAuctionItemsRequest,
        *,
        max_pages: int | None = None,
    ) -> FetchAuctionItemsResponse:
        """Fetch listing pages until exhausted or until max_pages is reached."""

        started_at = _utc_now()
        metrics = ScrapeRunMetrics(started_at=started_at)
        self.run_logger.run_started(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            adapter_version=self.adapter_version,
            parser_version=self.parser_version,
            started_at=started_at,
        )

        page_limit = max_pages or self.config.max_pages_per_run
        cursor = request.page_cursor
        items: list[RawAuctionItemObservation] = []
        errors: list[ModuleError] = []
        next_cursor: str | None = cursor

        for _ in range(max(1, page_limit)):
            page_request = replace(request, page_cursor=cursor)
            response = self._fetch_page(page_request, metrics=metrics)
            items.extend(response.items)
            errors.extend(response.errors)
            next_cursor = response.next_page_cursor
            if response.errors or not next_cursor:
                break
            cursor = next_cursor

        completed_at = _utc_now()
        metrics.completed_at = completed_at
        self.run_logger.run_completed(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            status="failed" if errors and not items else "completed",
            metrics=metrics.to_dict(),
            completed_at=completed_at,
        )
        return FetchAuctionItemsResponse(items=items, next_page_cursor=next_cursor, errors=errors)

    def _fetch_page(
        self,
        request: FetchAuctionItemsRequest,
        *,
        metrics: ScrapeRunMetrics,
    ) -> FetchAuctionItemsResponse:
        marketplace_code = str(request.marketplace_code.value if hasattr(request.marketplace_code, "value") else request.marketplace_code)
        if marketplace_code != MarketplaceCode.DROPCATCH.value:
            error = ModuleError(
                code="unsupported_marketplace",
                message="DropCatch adapter only accepts marketplace_code=dropcatch.",
                details={"marketplace_code": marketplace_code},
            )
            metrics.errors += 1
            return FetchAuctionItemsResponse(items=[], errors=[error])

        captured_at = _utc_now()
        url = self._resolve_page_url(request.page_cursor)
        if url is None:
            error = ModuleError(
                code="source_unavailable",
                message="DropCatch listing URL is not configured for this adapter instance.",
                details={"marketplace_code": marketplace_code},
            )
            metrics.errors += 1
            self._log_error(request, error, occurred_at=captured_at)
            return FetchAuctionItemsResponse(items=[], errors=[error])
        metrics.pages_attempted += 1
        self.run_logger.page_started(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            url=url,
            page_cursor=request.page_cursor,
            started_at=captured_at,
        )

        try:
            fetched_page = self.fetcher.fetch(
                url,
                headers=self._request_headers(),
                timeout_seconds=self.config.request_timeout_seconds,
            )
        except PageFetchError as exc:
            error = ModuleError(
                code=exc.code,
                message=str(exc),
                details={
                    "url": url,
                    "status_code": exc.status_code,
                    "retryable": exc.retryable,
                },
            )
            metrics.errors += 1
            self._log_error(request, error, occurred_at=_utc_now())
            return FetchAuctionItemsResponse(items=[], errors=[error])

        try:
            parsed_page = parse_dropcatch_listing_page(fetched_page.text, page_url=fetched_page.url)
        except Exception as exc:  # pragma: no cover - defensive boundary for source changes
            error = ModuleError(
                code="parse_error",
                message="DropCatch page could not be parsed into auction listings.",
                details={"url": fetched_page.url, "error_type": type(exc).__name__},
            )
            metrics.errors += 1
            self._log_error(request, error, occurred_at=_utc_now())
            return FetchAuctionItemsResponse(items=[], errors=[error])

        items: list[RawAuctionItemObservation] = []
        duplicate_count = 0
        for listing in parsed_page.listings[: max(0, request.limit)]:
            raw_payload = listing.raw_payload
            raw_payload_hash = stable_payload_hash(_hashable_raw_payload(raw_payload))
            dedup_key = DeduplicationKey(
                marketplace_code=MarketplaceCode.DROPCATCH.value,
                source_item_id=listing.source_listing_id,
                raw_payload_hash=raw_payload_hash,
            )
            if self.dedup_store.seen_before(dedup_key):
                duplicate_count += 1
                continue
            self.dedup_store.mark_seen(dedup_key, observed_at=captured_at)
            items.append(
                RawAuctionItemObservation(
                    marketplace_code=MarketplaceCode.DROPCATCH,
                    source_item_id=listing.source_listing_id,
                    source_url=listing.listing_url or fetched_page.url,
                    captured_at=captured_at,
                    raw_payload_json=raw_payload,
                    raw_payload_hash=raw_payload_hash,
                    adapter_version=self.adapter_version,
                    parser_version=self.parser_version,
                )
            )

        metrics.pages_succeeded += 1
        metrics.items_seen += len(parsed_page.listings)
        metrics.items_emitted += len(items)
        metrics.duplicate_items += duplicate_count
        self.run_logger.page_completed(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            url=fetched_page.url,
            item_count=len(parsed_page.listings),
            emitted_count=len(items),
            duplicate_count=duplicate_count,
            next_page_cursor=parsed_page.next_page_cursor,
            completed_at=_utc_now(),
        )
        return FetchAuctionItemsResponse(items=items, next_page_cursor=parsed_page.next_page_cursor, errors=parsed_page.errors)

    def _resolve_page_url(self, page_cursor: str | None) -> str | None:
        if page_cursor:
            parsed = urlparse(page_cursor)
            if parsed.scheme and parsed.netloc:
                return page_cursor
            if self.config.default_listing_url and page_cursor.startswith("/"):
                return urljoin(self.config.default_listing_url, page_cursor)
            return page_cursor
        return self.config.default_listing_url

    def _request_headers(self) -> Mapping[str, str]:
        return {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _log_error(self, request: FetchAuctionItemsRequest, error: ModuleError, *, occurred_at: datetime) -> None:
        self.run_logger.error_recorded(
            ingest_run_id=request.ingest_run_id,
            source_name=self.source_name,
            error_code=error.code,
            error_summary=error.message,
            details=error.details,
            occurred_at=occurred_at,
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hashable_raw_payload(raw_payload: Mapping[str, object]) -> Mapping[str, object]:
    return {
        key: value
        for key, value in raw_payload.items()
        if key not in {"page_url"}
    }
