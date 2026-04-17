"""Collector for Hacker News developer and startup signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from collectors.base import build_content_hash, fetch_json
from core.logging import get_logger
from models import ContentItem, SourceType


logger = get_logger("collectors.hackernews")

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
HN_ITEM_LINK = "https://news.ycombinator.com/item?id={item_id}"


@dataclass(frozen=True)
class HackerNewsCollector:
    """Collect top Hacker News stories and normalize them into ContentItem rows."""

    limit: int = 20

    def collect(self) -> list[ContentItem]:
        story_ids = fetch_json(HN_TOP_STORIES_URL) or []
        items: list[ContentItem] = []
        fetched_at = datetime.now(timezone.utc)

        for item_id in story_ids[: self.limit]:
            payload = fetch_json(HN_ITEM_URL.format(item_id=item_id))
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "story":
                continue

            title = str(payload.get("title") or "").strip()
            if not title:
                continue

            url = str(payload.get("url") or HN_ITEM_LINK.format(item_id=item_id)).strip()
            published_at = None
            if payload.get("time"):
                published_at = datetime.fromtimestamp(int(payload["time"]), tz=timezone.utc)

            items.append(
                ContentItem(
                    source_name="hacker_news",
                    source_type=SourceType.DEVELOPER,
                    title=title,
                    url=url,
                    body=str(payload.get("text") or ""),
                    summary="",
                    author=str(payload.get("by") or ""),
                    published_at=published_at,
                    fetched_at=fetched_at,
                    content_hash=build_content_hash("hn", title, url),
                    tags=("hackernews", "developer_signal"),
                    raw_payload=payload,
                )
            )

        logger.info("Collected %s Hacker News items.", len(items))
        return items
