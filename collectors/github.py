"""Collector for GitHub repository and release-adjacent signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from collectors.base import build_content_hash, fetch_json
from config.runtime import get_runtime_secret
from core.logging import get_logger
from models import ContentItem, SourceType


logger = get_logger("collectors.github")


@dataclass(frozen=True)
class GitHubCollector:
    """Collect recently active GitHub repositories using the search API."""

    limit: int = 20
    min_stars: int = 5
    lookback_days: int = 14

    def collect(self) -> list[ContentItem]:
        since = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")
        query = quote(f"pushed:>={since} stars:>={self.min_stars}")
        url = (
            "https://api.github.com/search/repositories"
            f"?q={query}&sort=updated&order=desc&per_page={self.limit}"
        )
        token = get_runtime_secret("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = fetch_json(url, headers=headers) or {}
        repositories = payload.get("items", []) if isinstance(payload, dict) else []
        items: list[ContentItem] = []
        fetched_at = datetime.now(timezone.utc)

        for repo in repositories:
            if not isinstance(repo, dict):
                continue
            full_name = str(repo.get("full_name") or "").strip()
            html_url = str(repo.get("html_url") or "").strip()
            if not full_name or not html_url:
                continue

            description = str(repo.get("description") or "")
            published_at = None
            updated_at = repo.get("updated_at")
            if updated_at:
                published_at = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))

            tags = ["github", "open_source", "repository_signal"]
            language = str(repo.get("language") or "").strip()
            if language:
                tags.append(language.lower())

            items.append(
                ContentItem(
                    source_name="github",
                    source_type=SourceType.REPOSITORY,
                    title=full_name,
                    url=html_url,
                    body=description,
                    summary=description,
                    author=str((repo.get("owner") or {}).get("login") or ""),
                    published_at=published_at,
                    fetched_at=fetched_at,
                    content_hash=build_content_hash("github", full_name, html_url, description),
                    tags=tuple(tags),
                    raw_payload=repo,
                )
            )

        logger.info("Collected %s GitHub repository items.", len(items))
        return items
