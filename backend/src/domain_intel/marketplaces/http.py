"""Safe HTTP transport for marketplace adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Mapping
from urllib import error, request, robotparser
from urllib.parse import urlparse

from domain_intel.marketplaces.base import PageFetchError, PageFetcher
from domain_intel.marketplaces.schemas import FetchedPage


RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class RetryPolicy:
    """Retry settings for source page requests."""

    max_attempts: int = 3
    backoff_seconds: float = 1.5
    retryable_status_codes: set[int] = field(default_factory=lambda: set(RETRYABLE_STATUS_CODES))


@dataclass(frozen=True)
class SafeHttpConfig:
    """Operational safeguards for marketplace HTTP access."""

    user_agent: str = "DomainIntelBot/0.1 (+https://example.invalid/contact)"
    timeout_seconds: float = 20.0
    allowed_hosts: tuple[str, ...] = ()
    min_delay_between_requests_seconds: float = 1.0
    respect_robots_txt: bool = True
    fail_closed_on_robots_error: bool = True
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


class SafeHttpPageFetcher(PageFetcher):
    """urllib-based fetcher with retries, rate limits, and robots awareness."""

    def __init__(self, config: SafeHttpConfig | None = None) -> None:
        self.config = config or SafeHttpConfig()
        self._last_request_at: float | None = None
        self._robots_by_origin: dict[str, robotparser.RobotFileParser] = {}

    def fetch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> FetchedPage:
        self._validate_url(url)
        self._ensure_robots_allowed(url)

        merged_headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if headers:
            merged_headers.update(headers)

        attempts = max(1, self.config.retry_policy.max_attempts)
        last_error: PageFetchError | None = None
        for attempt in range(1, attempts + 1):
            self._respect_rate_limit()
            try:
                request_obj = request.Request(url, headers=merged_headers, method="GET")
                with request.urlopen(  # nosec B310 - URL is validated and host-limited by config.
                    request_obj,
                    timeout=timeout_seconds or self.config.timeout_seconds,
                ) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    text = response.read().decode(charset, errors="replace")
                    return FetchedPage(
                        url=response.geturl(),
                        status_code=int(response.status),
                        text=text,
                        headers=dict(response.headers.items()),
                    )
            except error.HTTPError as exc:
                retry_after = self._retry_after_seconds(exc.headers.get("Retry-After"))
                retryable = exc.code in self.config.retry_policy.retryable_status_codes
                last_error = PageFetchError(
                    f"HTTP {exc.code} while fetching marketplace page",
                    code="http_error",
                    status_code=exc.code,
                    retryable=retryable,
                )
                if attempt >= attempts or not retryable:
                    break
                self._sleep_before_retry(attempt, retry_after)
            except (TimeoutError, error.URLError) as exc:
                last_error = PageFetchError(
                    "Network error while fetching marketplace page",
                    code="network_error",
                    retryable=True,
                )
                if attempt >= attempts:
                    break
                self._sleep_before_retry(attempt, None)

        if last_error is not None:
            raise last_error
        raise PageFetchError("Unknown marketplace page fetch failure", code="page_fetch_failed")

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise PageFetchError("Only absolute http(s) URLs are allowed", code="invalid_url")
        if self.config.allowed_hosts and parsed.hostname not in self.config.allowed_hosts:
            raise PageFetchError(
                "Marketplace URL host is not in the adapter allowlist",
                code="host_not_allowed",
            )

    def _ensure_robots_allowed(self, url: str) -> None:
        if not self.config.respect_robots_txt:
            return

        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots = self._robots_by_origin.get(origin)
        if robots is None:
            robots_url = f"{origin}/robots.txt"
            robots = robotparser.RobotFileParser()
            robots.set_url(robots_url)
            try:
                robots.read()
            except Exception as exc:  # pragma: no cover - depends on remote server behavior
                if self.config.fail_closed_on_robots_error:
                    raise PageFetchError(
                        "Could not verify robots.txt for marketplace host",
                        code="robots_unverified",
                    ) from exc
            self._robots_by_origin[origin] = robots

        if not robots.can_fetch(self.config.user_agent, url):
            raise PageFetchError(
                "robots.txt disallows this marketplace URL for the configured user agent",
                code="robots_disallowed",
            )

    def _respect_rate_limit(self) -> None:
        if self._last_request_at is None:
            self._last_request_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.config.min_delay_between_requests_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _sleep_before_retry(self, attempt: int, retry_after_seconds: float | None) -> None:
        if retry_after_seconds is not None:
            time.sleep(retry_after_seconds)
            return
        time.sleep(self.config.retry_policy.backoff_seconds * attempt)

    @staticmethod
    def _retry_after_seconds(raw_value: str | None) -> float | None:
        if not raw_value:
            return None
        stripped = raw_value.strip()
        if stripped.isdigit():
            return float(stripped)
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        return max(0.0, retry_at.timestamp() - time.time())
