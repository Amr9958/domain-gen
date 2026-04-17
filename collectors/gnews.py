"""Collector for GNews free-tier trend validation signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from collectors.base import build_content_hash, fetch_json
from config.runtime import get_runtime_secret, get_runtime_value
from core.logging import get_logger
from models import ContentItem, SourceType


logger = get_logger("collectors.gnews")


@dataclass(frozen=True)
class GNewsCollector:
    """Collect GNews items when an API key is available."""

    limit: int = 20
    query: str = "AI OR startup OR developer tools OR open source"

    def collect(self) -> list[ContentItem]:
        api_key = get_runtime_secret("GNEWS_API_KEY")
        if not api_key:
            logger.info("Skipping GNews collection because GNEWS_API_KEY is not configured.")
            return []

        language = get_runtime_value("GNEWS_LANG", "en")
        country = get_runtime_value("GNEWS_COUNTRY", "us")
        url = (
            "https://gnews.io/api/v4/search"
            f"?q={quote(self.query)}&lang={quote(language)}&country={quote(country)}"
            f"&max={self.limit}&apikey={quote(api_key)}"
        )
        payload = fetch_json(url) or {}
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        items: list[ContentItem] = []
        fetched_at = datetime.now(timezone.utc)

        for article in articles:
            if not isinstance(article, dict):
                continue
            title = str(article.get("title") or "").strip()
            article_url = str(article.get("url") or "").strip()
            if not title or not article_url:
                continue

            published_at = None
            raw_published = article.get("publishedAt")
            if raw_published:
                published_at = datetime.fromisoformat(str(raw_published).replace("Z", "+00:00"))

            source = article.get("source") or {}
            source_name = str(source.get("name") or "gnews").strip().lower().replace(" ", "_")
            description = str(article.get("description") or "")
            content = str(article.get("content") or "")

            items.append(
                ContentItem(
                    source_name=source_name,
                    source_type=SourceType.NEWS,
                    title=title,
                    url=article_url,
                    body=content,
                    summary=description,
                    author="",
                    published_at=published_at,
                    fetched_at=fetched_at,
                    content_hash=build_content_hash("gnews", title, article_url, description),
                    tags=("gnews", "news_signal"),
                    raw_payload=article,
                )
            )

        logger.info("Collected %s GNews items.", len(items))
        return items
