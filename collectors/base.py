"""Base utilities for signal collectors."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha1
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.logging import get_logger


logger = get_logger("collectors.base")


@dataclass(frozen=True)
class CollectorResult:
    """Raw collector result for a single source run."""

    source_name: str
    items: list[dict[str, Any]]


def build_content_hash(*parts: object) -> str:
    """Create a stable hash for deduplication across sources."""
    raw = "||".join(str(part or "").strip().lower() for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()


def _retry_delay(attempt: int, exc: HTTPError | URLError | None = None) -> float:
    """Return a modest exponential backoff delay for retriable collector failures."""
    if isinstance(exc, HTTPError):
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return min(8.0, 1.5 * (2 ** max(0, attempt - 1)))


def _should_retry_http_error(exc: HTTPError) -> bool:
    """Retry transient API and rate-limit failures without masking permanent errors."""
    return exc.code in {403, 408, 425, 429, 500, 502, 503, 504}


def fetch_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    attempts: int = 3,
) -> Any:
    """Fetch JSON using the stdlib with lightweight retry and backoff behavior."""
    request = Request(
        url,
        headers={
            "User-Agent": "trend-domain-intelligence/0.1",
            **(headers or {}),
        },
    )
    for attempt in range(1, max(1, attempts) + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if attempt < attempts and _should_retry_http_error(exc):
                delay = _retry_delay(attempt, exc)
                logger.warning(
                    "HTTP error while fetching %s: %s. Retrying in %.1fs (%s/%s).",
                    url,
                    exc,
                    delay,
                    attempt,
                    attempts,
                )
                time.sleep(delay)
                continue
            logger.warning("HTTP error while fetching %s: %s", url, exc)
            break
        except URLError as exc:
            if attempt < attempts:
                delay = _retry_delay(attempt, exc)
                logger.warning(
                    "Network error while fetching %s: %s. Retrying in %.1fs (%s/%s).",
                    url,
                    exc,
                    delay,
                    attempt,
                    attempts,
                )
                time.sleep(delay)
                continue
            logger.warning("Network error while fetching %s: %s", url, exc)
            break
        except Exception as exc:  # pragma: no cover - runtime/network path
            logger.warning("Unexpected error while fetching %s: %s", url, exc)
            break
    return None
