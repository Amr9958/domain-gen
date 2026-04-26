"""Shared marketplace adapter protocols and retry utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from marketplaces.schemas import AdapterError


class HttpClient(Protocol):
    """Minimal HTTP client interface used by marketplace adapters."""

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> str:
        """Fetch a URL and return the response body as text."""


class ScrapeRunLogger(Protocol):
    """Hook interface for scrape-run logging without coupling adapters to a DB."""

    def page_started(self, *, ingest_run_id: str, marketplace_code: str, page_url: str) -> None:
        """Record that a source page fetch has started."""

    def page_completed(
        self,
        *,
        ingest_run_id: str,
        marketplace_code: str,
        page_url: str,
        item_count: int,
        next_page_cursor: str | None,
    ) -> None:
        """Record that a source page fetch completed."""

    def page_failed(
        self,
        *,
        ingest_run_id: str,
        marketplace_code: str,
        page_url: str,
        error: AdapterError,
        retry_count: int,
    ) -> None:
        """Record that a source page fetch failed."""


@dataclass(frozen=True)
class RetryPolicy:
    """Conservative retry behavior for transient source access failures."""

    attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 6.0
    retry_statuses: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

    def delay_for_attempt(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        delay = self.initial_delay_seconds * (2 ** max(0, attempt - 1))
        return min(self.max_delay_seconds, delay)


class UrllibHttpClient:
    """Stdlib HTTP client for simple marketplace page fetches."""

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> str:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")


class NoopScrapeRunLogger:
    """Default logging hook used when no persistence layer is wired yet."""

    def page_started(self, *, ingest_run_id: str, marketplace_code: str, page_url: str) -> None:
        _ = (ingest_run_id, marketplace_code, page_url)

    def page_completed(
        self,
        *,
        ingest_run_id: str,
        marketplace_code: str,
        page_url: str,
        item_count: int,
        next_page_cursor: str | None,
    ) -> None:
        _ = (ingest_run_id, marketplace_code, page_url, item_count, next_page_cursor)

    def page_failed(
        self,
        *,
        ingest_run_id: str,
        marketplace_code: str,
        page_url: str,
        error: AdapterError,
        retry_count: int,
    ) -> None:
        _ = (ingest_run_id, marketplace_code, page_url, error, retry_count)


def fetch_with_retries(
    *,
    client: HttpClient,
    url: str,
    headers: dict[str, str],
    timeout: int,
    retry_policy: RetryPolicy,
) -> tuple[str | None, AdapterError | None, int]:
    """Fetch text with bounded retries and stable error codes."""
    attempts = max(1, retry_policy.attempts)
    for attempt in range(1, attempts + 1):
        try:
            return client.get(url, headers=headers, timeout=timeout), None, attempt - 1
        except HTTPError as exc:
            can_retry = exc.code in retry_policy.retry_statuses and attempt < attempts
            if can_retry:
                delay = retry_policy.delay_for_attempt(
                    attempt,
                    exc.headers.get("Retry-After") if exc.headers else None,
                )
                time.sleep(delay)
                continue
            code = "source_rate_limited" if exc.code == 429 else "source_unavailable"
            return (
                None,
                AdapterError(
                    code=code,
                    message=f"Source returned HTTP {exc.code}.",
                    details={"status_code": exc.code, "url": url},
                ),
                attempt - 1,
            )
        except URLError as exc:
            if attempt < attempts:
                time.sleep(retry_policy.delay_for_attempt(attempt))
                continue
            return (
                None,
                AdapterError(
                    code="source_unavailable",
                    message="Network error while fetching source page.",
                    details={"reason": str(exc.reason), "url": url},
                ),
                attempt - 1,
            )
        except Exception as exc:  # pragma: no cover - defensive runtime path
            return (
                None,
                AdapterError(
                    code="source_unavailable",
                    message="Unexpected error while fetching source page.",
                    details={"error": str(exc), "url": url},
                ),
                attempt - 1,
            )

    return (
        None,
        AdapterError(
            code="source_unavailable",
            message="Source page fetch failed after retries.",
            details={"url": url},
        ),
        attempts - 1,
    )
