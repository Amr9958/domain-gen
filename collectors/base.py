"""Base utilities for signal collectors."""

from __future__ import annotations

import json
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


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    """Fetch JSON using the stdlib so collectors need no heavy HTTP dependency."""
    request = Request(
        url,
        headers={
            "User-Agent": "trend-domain-intelligence/0.1",
            **(headers or {}),
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logger.warning("HTTP error while fetching %s: %s", url, exc)
    except URLError as exc:
        logger.warning("Network error while fetching %s: %s", url, exc)
    except Exception as exc:  # pragma: no cover - runtime/network path
        logger.warning("Unexpected error while fetching %s: %s", url, exc)
    return None
