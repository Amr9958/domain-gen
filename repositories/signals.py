"""Repositories for collected and processed signal items."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from config import get_settings
from core.logging import get_logger
from integrations import get_supabase_manager
from jobs.runtime import JobContext
from models import (
    ContentItem,
    DomainOpportunity,
    DomainRecommendation,
    ItemClassification,
    KeywordInsight,
    ProcessedSignal,
    SourceType,
    Theme,
)


logger = get_logger("repositories.signals")


def _serialize_datetime(value: datetime | None) -> str | None:
    """Convert datetimes to ISO strings for JSONL and Supabase payloads."""
    if value is None:
        return None
    return value.isoformat()


def _parse_datetime(value: object) -> datetime | None:
    """Parse ISO datetimes from persisted local or cloud rows."""
    if value in ("", None):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _serialize_run(job: JobContext) -> dict[str, Any]:
    """Convert a job context into a JSON-safe persistence payload."""
    payload = asdict(job.run)
    payload["started_at"] = _serialize_datetime(job.run.started_at)
    payload["ended_at"] = _serialize_datetime(job.run.ended_at)
    return payload


def _serialize_content_item(
    item: ContentItem,
    *,
    ingest_run_id: str | None = None,
    is_processed: bool = False,
    processed_run_id: str = "",
    processed_at: datetime | None = None,
    cluster_key: str = "",
    cluster_terms: tuple[str, ...] = (),
    classification: str = "",
    theme_name: str = "",
    theme_description: str = "",
    signal_score: float = 0.0,
    reasons: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Serialize a collected item with raw or processed pipeline metadata."""
    payload = {
        "source_name": item.source_name,
        "source_type": str(item.source_type),
        "title": item.title,
        "url": item.url,
        "body": item.body,
        "summary": item.summary,
        "author": item.author,
        "language": item.language,
        "content_hash": item.content_hash,
        "cluster_key": cluster_key,
        "cluster_terms": list(cluster_terms),
        "classification": classification,
        "theme_name": theme_name,
        "theme_description": theme_description,
        "signal_score": signal_score,
        "published_at": _serialize_datetime(item.published_at),
        "fetched_at": _serialize_datetime(item.fetched_at),
        "tags": list(item.tags),
        "raw_payload": dict(item.raw_payload),
        "reasons": list(reasons),
        "is_processed": is_processed,
        "processed_run_id": processed_run_id,
        "processed_at": _serialize_datetime(processed_at),
    }
    if ingest_run_id is not None:
        payload["ingest_run_id"] = ingest_run_id
    return payload


def _deserialize_content_item(row: dict[str, Any]) -> ContentItem:
    """Rebuild a typed ContentItem from repository storage rows."""
    tags = row.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]

    raw_payload = row.get("raw_payload") or {}
    if not isinstance(raw_payload, dict):
        raw_payload = {}

    source_type_raw = str(row.get("source_type") or SourceType.NEWS)
    try:
        source_type = SourceType(source_type_raw)
    except ValueError:
        source_type = SourceType.NEWS

    return ContentItem(
        source_name=str(row.get("source_name") or ""),
        source_type=source_type,
        title=str(row.get("title") or ""),
        url=str(row.get("url") or ""),
        body=str(row.get("body") or ""),
        summary=str(row.get("summary") or ""),
        author=str(row.get("author") or ""),
        language=str(row.get("language") or "en"),
        content_hash=str(row.get("content_hash") or ""),
        published_at=_parse_datetime(row.get("published_at")),
        fetched_at=_parse_datetime(row.get("fetched_at")) or datetime.utcnow(),
        tags=tuple(str(tag) for tag in tags if str(tag).strip()),
        raw_payload=raw_payload,
    )


def _parse_item_classification(value: object) -> ItemClassification:
    """Parse stored classification text into the shared enum."""
    raw_value = str(value or ItemClassification.WATCHLIST.value)
    try:
        return ItemClassification(raw_value)
    except ValueError:
        return ItemClassification.WATCHLIST


def _parse_domain_recommendation(value: object) -> DomainRecommendation:
    """Parse stored recommendation text into the shared enum."""
    raw_value = str(value or DomainRecommendation.WATCH.value)
    try:
        return DomainRecommendation(raw_value)
    except ValueError:
        return DomainRecommendation.WATCH


def _serialize_processed_signal(signal: ProcessedSignal, run_id: str) -> dict[str, Any]:
    """Serialize a processed signal row for processed persistence layers."""
    return _serialize_content_item(
        signal.item,
        ingest_run_id=None,
        is_processed=True,
        processed_run_id=run_id,
        processed_at=datetime.utcnow(),
        cluster_key=signal.cluster_key,
        cluster_terms=signal.cluster_terms,
        classification=signal.classification.value,
        theme_name=signal.theme_name,
        theme_description=signal.theme_description,
        signal_score=signal.signal_score,
        reasons=signal.reasons,
    )


def _serialize_theme(theme: Theme) -> dict[str, Any]:
    """Serialize a Theme dataclass for JSONL and Supabase writes."""
    return {
        "canonical_name": theme.canonical_name,
        "description": theme.description,
        "classification": theme.classification.value,
        "source_count": theme.source_count,
        "first_seen_at": _serialize_datetime(theme.first_seen_at),
        "last_seen_at": _serialize_datetime(theme.last_seen_at),
        "momentum_score": theme.momentum_score,
        "related_terms": list(theme.related_terms),
        "source_names": list(theme.source_names),
        "source_types": list(theme.source_types),
        "source_tags": list(theme.source_tags),
        "source_entities": list(theme.source_entities),
        "source_breakdown": list(theme.source_breakdown),
        "cluster_keys": list(theme.cluster_keys),
        "evidence_titles": list(theme.evidence_titles),
        "reason_highlights": list(theme.reason_highlights),
    }


def _serialize_keyword_insight(keyword: KeywordInsight) -> dict[str, Any]:
    """Serialize a keyword insight for local storage or Supabase writes."""
    return {
        "keyword": keyword.keyword,
        "keyword_type": keyword.keyword_type,
        "theme_name": keyword.theme_name,
        "classification": keyword.classification.value,
        "niche": keyword.niche,
        "buyer_type": keyword.buyer_type,
        "commercial_score": keyword.commercial_score,
        "novelty_score": keyword.novelty_score,
        "brandability_score": keyword.brandability_score,
        "notes": keyword.notes,
    }


def _deserialize_theme(row: dict[str, Any]) -> Theme:
    """Rebuild a Theme row from local JSONL or Supabase data."""
    related_terms = row.get("related_terms") or []
    if not isinstance(related_terms, list):
        related_terms = [str(related_terms)]
    source_names = row.get("source_names") or []
    if not isinstance(source_names, list):
        source_names = [str(source_names)]
    source_types = row.get("source_types") or []
    if not isinstance(source_types, list):
        source_types = [str(source_types)]
    source_tags = row.get("source_tags") or []
    if not isinstance(source_tags, list):
        source_tags = [str(source_tags)]
    source_entities = row.get("source_entities") or []
    if not isinstance(source_entities, list):
        source_entities = [str(source_entities)]
    source_breakdown = row.get("source_breakdown") or []
    if not isinstance(source_breakdown, list):
        source_breakdown = [str(source_breakdown)]
    cluster_keys = row.get("cluster_keys") or []
    if not isinstance(cluster_keys, list):
        cluster_keys = [str(cluster_keys)]
    evidence_titles = row.get("evidence_titles") or []
    if not isinstance(evidence_titles, list):
        evidence_titles = [str(evidence_titles)]
    reason_highlights = row.get("reason_highlights") or []
    if not isinstance(reason_highlights, list):
        reason_highlights = [str(reason_highlights)]
    return Theme(
        canonical_name=str(row.get("canonical_name") or ""),
        description=str(row.get("description") or ""),
        classification=_parse_item_classification(row.get("classification")),
        source_count=int(row.get("source_count") or 0),
        first_seen_at=_parse_datetime(row.get("first_seen_at")) or datetime.utcnow(),
        last_seen_at=_parse_datetime(row.get("last_seen_at")) or datetime.utcnow(),
        momentum_score=float(row.get("momentum_score") or 0),
        related_terms=tuple(str(term) for term in related_terms if str(term).strip()),
        source_names=tuple(str(name) for name in source_names if str(name).strip()),
        source_types=tuple(str(source_type) for source_type in source_types if str(source_type).strip()),
        source_tags=tuple(str(tag) for tag in source_tags if str(tag).strip()),
        source_entities=tuple(str(entity) for entity in source_entities if str(entity).strip()),
        source_breakdown=tuple(str(entry) for entry in source_breakdown if str(entry).strip()),
        cluster_keys=tuple(str(entry) for entry in cluster_keys if str(entry).strip()),
        evidence_titles=tuple(str(entry) for entry in evidence_titles if str(entry).strip()),
        reason_highlights=tuple(str(entry) for entry in reason_highlights if str(entry).strip()),
    )


def _deserialize_keyword_insight(row: dict[str, Any]) -> KeywordInsight:
    """Rebuild a KeywordInsight row from local JSONL or Supabase data."""
    return KeywordInsight(
        keyword=str(row.get("keyword") or ""),
        keyword_type=str(row.get("keyword_type") or ""),
        theme_name=str(row.get("theme_name") or ""),
        classification=_parse_item_classification(row.get("classification")),
        niche=str(row.get("niche") or ""),
        buyer_type=str(row.get("buyer_type") or ""),
        commercial_score=float(row.get("commercial_score") or 0),
        novelty_score=float(row.get("novelty_score") or 0),
        brandability_score=float(row.get("brandability_score") or 0),
        notes=str(row.get("notes") or ""),
    )


def _serialize_domain_opportunity(opportunity: DomainOpportunity) -> dict[str, Any]:
    """Serialize a domain opportunity for local storage or Supabase writes."""
    return {
        "domain_name": opportunity.domain_name,
        "extension": opportunity.extension,
        "source_theme": opportunity.source_theme,
        "recommendation": opportunity.recommendation.value,
        "keyword": opportunity.keyword,
        "niche": opportunity.niche,
        "buyer_type": opportunity.buyer_type,
        "style": opportunity.style,
        "score": opportunity.score,
        "review_bucket": opportunity.review_bucket,
        "scoring_profile": opportunity.scoring_profile,
        "grade": opportunity.grade,
        "value_estimate": opportunity.value_estimate,
        "rationale": opportunity.rationale,
        "risk_notes": list(opportunity.risk_notes),
        "rejected_reason": opportunity.rejected_reason,
    }


def _deserialize_domain_opportunity(row: dict[str, Any]) -> DomainOpportunity:
    """Rebuild a DomainOpportunity row from local JSONL or Supabase data."""
    risk_notes = row.get("risk_notes") or []
    if not isinstance(risk_notes, list):
        risk_notes = [str(risk_notes)]
    return DomainOpportunity(
        domain_name=str(row.get("domain_name") or ""),
        extension=str(row.get("extension") or ""),
        source_theme=str(row.get("source_theme") or ""),
        recommendation=_parse_domain_recommendation(row.get("recommendation")),
        keyword=str(row.get("keyword") or ""),
        niche=str(row.get("niche") or ""),
        buyer_type=str(row.get("buyer_type") or ""),
        style=str(row.get("style") or ""),
        score=float(row.get("score") or 0),
        review_bucket=str(row.get("review_bucket") or ""),
        scoring_profile=str(row.get("scoring_profile") or ""),
        grade=str(row.get("grade") or ""),
        value_estimate=str(row.get("value_estimate") or ""),
        rationale=str(row.get("rationale") or ""),
        risk_notes=tuple(str(note) for note in risk_notes if str(note).strip()),
        rejected_reason=str(row.get("rejected_reason") or ""),
    )


class SignalRepository(Protocol):
    """Persistence contract for signal pipeline outputs."""

    def save_run(self, job: JobContext) -> None:
        """Persist run metadata."""

    def save_raw_items(self, items: list[ContentItem], run_id: str = "") -> None:
        """Persist raw collected items."""

    def list_raw_items(self, only_unprocessed: bool = False) -> list[ContentItem]:
        """Load raw items for downstream processing."""

    def list_themes(self) -> list[Theme]:
        """Load extracted themes for downstream jobs."""

    def list_keywords(self) -> list[KeywordInsight]:
        """Load extracted keyword insights for downstream jobs."""

    def list_domain_ideas(self) -> list[DomainOpportunity]:
        """Load generated domain ideas for downstream dashboards."""

    def save_processed_items(self, items: list[ProcessedSignal], run_id: str = "") -> None:
        """Persist processed items."""

    def save_themes(self, themes: list[Theme]) -> None:
        """Persist extracted themes."""

    def save_keywords(self, keywords: list[KeywordInsight]) -> None:
        """Persist extracted keyword intelligence rows."""

    def save_domain_ideas(self, opportunities: list[DomainOpportunity]) -> None:
        """Persist generated domain opportunities."""


class LocalSignalRepository:
    """Local JSONL fallback used when Supabase is not enabled."""

    def __init__(self) -> None:
        self.base_dir = get_settings().data_dir / "signals"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.raw_path = self.base_dir / "raw_items.jsonl"
        self.processed_path = self.base_dir / "processed_items.jsonl"
        self.runs_path = self.base_dir / "runs.jsonl"
        self.themes_path = self.base_dir / "themes.jsonl"
        self.keywords_path = self.base_dir / "keywords.jsonl"
        self.domain_ideas_path = self.base_dir / "domain_ideas.jsonl"

    def _append_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, default=str, ensure_ascii=True) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def _latest_rows_by_key(self, path: Path, key_name: str) -> dict[str, dict[str, Any]]:
        latest_rows: dict[str, dict[str, Any]] = {}
        for row in self._read_jsonl(path):
            key = str(row.get(key_name) or "").strip()
            if not key:
                continue
            latest_rows[key] = row
        return latest_rows

    def save_run(self, job: JobContext) -> None:
        self._append_jsonl(self.runs_path, [_serialize_run(job)])

    def save_raw_items(self, items: list[ContentItem], run_id: str = "") -> None:
        rows = [
            _serialize_content_item(
                item,
                ingest_run_id=run_id,
                is_processed=False,
            )
            for item in items
        ]
        self._append_jsonl(self.raw_path, rows)

    def list_raw_items(self, only_unprocessed: bool = False) -> list[ContentItem]:
        latest_rows = self._latest_rows_by_key(self.raw_path, "content_hash")
        rows = list(latest_rows.values())
        if only_unprocessed:
            rows = [row for row in rows if not row.get("is_processed", False)]
        rows.sort(key=lambda row: str(row.get("fetched_at") or ""), reverse=True)
        return [_deserialize_content_item(row) for row in rows]

    def list_themes(self) -> list[Theme]:
        latest_rows = self._latest_rows_by_key(self.themes_path, "canonical_name")
        rows = list(latest_rows.values())
        rows.sort(key=lambda row: float(row.get("momentum_score") or 0), reverse=True)
        return [_deserialize_theme(row) for row in rows]

    def list_keywords(self) -> list[KeywordInsight]:
        latest_rows: dict[str, dict[str, Any]] = {}
        for row in self._read_jsonl(self.keywords_path):
            key = "||".join(
                [
                    str(row.get("theme_name") or "").strip(),
                    str(row.get("keyword") or "").strip(),
                    str(row.get("keyword_type") or "").strip(),
                ]
            )
            if key.strip("|"):
                latest_rows[key] = row
        rows = list(latest_rows.values())
        rows.sort(key=lambda row: float(row.get("commercial_score") or 0), reverse=True)
        return [_deserialize_keyword_insight(row) for row in rows]

    def list_domain_ideas(self) -> list[DomainOpportunity]:
        latest_rows: dict[str, dict[str, Any]] = {}
        for row in self._read_jsonl(self.domain_ideas_path):
            key = "||".join(
                [
                    str(row.get("source_theme") or "").strip(),
                    str(row.get("domain_name") or "").strip(),
                    str(row.get("extension") or "").strip(),
                ]
            )
            if key.strip("|"):
                latest_rows[key] = row
        rows = list(latest_rows.values())
        review_bucket_rank = {"shortlist": 2, "watchlist": 1, "rejected": 0}
        recommendation_rank = {"buy": 2, "watch": 1, "skip": 0}
        rows.sort(
            key=lambda row: (
                review_bucket_rank.get(str(row.get("review_bucket") or ""), -1),
                recommendation_rank.get(str(row.get("recommendation") or ""), -1),
                float(row.get("score") or 0),
            ),
            reverse=True,
        )
        return [_deserialize_domain_opportunity(row) for row in rows]

    def _mark_raw_items_processed(self, items: list[ProcessedSignal], run_id: str) -> None:
        latest_rows = self._latest_rows_by_key(self.raw_path, "content_hash")
        processed_rows: list[dict[str, Any]] = []
        processed_at = datetime.utcnow()
        for signal in items:
            original_row = latest_rows.get(signal.item.content_hash)
            if original_row is None:
                continue
            processed_rows.append(
                {
                    **original_row,
                    "is_processed": True,
                    "processed_run_id": run_id,
                    "processed_at": _serialize_datetime(processed_at),
                    "cluster_key": signal.cluster_key,
                    "cluster_terms": list(signal.cluster_terms),
                    "classification": signal.classification.value,
                    "theme_name": signal.theme_name,
                    "theme_description": signal.theme_description,
                    "signal_score": signal.signal_score,
                    "reasons": list(signal.reasons),
                }
            )
        self._append_jsonl(self.raw_path, processed_rows)

    def save_processed_items(self, items: list[ProcessedSignal], run_id: str = "") -> None:
        rows = [_serialize_processed_signal(signal, run_id) for signal in items]
        self._append_jsonl(self.processed_path, rows)
        self._mark_raw_items_processed(items, run_id)

    def save_themes(self, themes: list[Theme]) -> None:
        self._append_jsonl(self.themes_path, [_serialize_theme(theme) for theme in themes])

    def save_keywords(self, keywords: list[KeywordInsight]) -> None:
        self._append_jsonl(self.keywords_path, [_serialize_keyword_insight(keyword) for keyword in keywords])

    def save_domain_ideas(self, opportunities: list[DomainOpportunity]) -> None:
        self._append_jsonl(
            self.domain_ideas_path,
            [_serialize_domain_opportunity(opportunity) for opportunity in opportunities],
        )


class SupabaseSignalRepository:
    """Supabase-backed signal repository for Phase 2 data."""

    def __init__(self) -> None:
        self.manager = get_supabase_manager()

    def save_run(self, job: JobContext) -> None:
        table = self.manager.table("runs")
        if table is None:
            return
        table.upsert(_serialize_run(job), on_conflict="run_id").execute()

    def save_raw_items(self, items: list[ContentItem], run_id: str = "") -> None:
        table = self.manager.table("content_items")
        if table is None or not items:
            return
        rows = [
            _serialize_content_item(
                item,
                ingest_run_id=run_id,
                is_processed=False,
            )
            for item in items
        ]
        table.upsert(rows, on_conflict="content_hash").execute()

    def list_raw_items(self, only_unprocessed: bool = False) -> list[ContentItem]:
        table = self.manager.table("content_items")
        if table is None:
            return []
        query = table.select("*")
        if only_unprocessed:
            query = query.eq("is_processed", False)
        result = query.execute()
        rows = getattr(result, "data", []) or []
        return [_deserialize_content_item(row) for row in rows if isinstance(row, dict)]

    def list_themes(self) -> list[Theme]:
        table = self.manager.table("themes")
        if table is None:
            return []
        result = table.select("*").execute()
        rows = getattr(result, "data", []) or []
        return [_deserialize_theme(row) for row in rows if isinstance(row, dict)]

    def list_keywords(self) -> list[KeywordInsight]:
        table = self.manager.table("keywords")
        if table is None:
            return []
        result = table.select("*").execute()
        rows = getattr(result, "data", []) or []
        return [_deserialize_keyword_insight(row) for row in rows if isinstance(row, dict)]

    def list_domain_ideas(self) -> list[DomainOpportunity]:
        table = self.manager.table("domain_ideas")
        if table is None:
            return []
        result = table.select("*").execute()
        rows = getattr(result, "data", []) or []
        return [_deserialize_domain_opportunity(row) for row in rows if isinstance(row, dict)]

    def save_processed_items(self, items: list[ProcessedSignal], run_id: str = "") -> None:
        table = self.manager.table("content_items")
        if table is None or not items:
            return
        rows = [_serialize_processed_signal(signal, run_id) for signal in items]
        table.upsert(rows, on_conflict="content_hash").execute()

    def save_themes(self, themes: list[Theme]) -> None:
        table = self.manager.table("themes")
        if table is None or not themes:
            return
        rows = [_serialize_theme(theme) for theme in themes]
        table.upsert(rows, on_conflict="canonical_name").execute()

    def save_keywords(self, keywords: list[KeywordInsight]) -> None:
        table = self.manager.table("keywords")
        if table is None or not keywords:
            return
        rows = [_serialize_keyword_insight(keyword) for keyword in keywords]
        table.upsert(rows, on_conflict="theme_name,keyword,keyword_type").execute()

    def save_domain_ideas(self, opportunities: list[DomainOpportunity]) -> None:
        table = self.manager.table("domain_ideas")
        if table is None or not opportunities:
            return
        rows = [_serialize_domain_opportunity(opportunity) for opportunity in opportunities]
        table.upsert(rows, on_conflict="source_theme,domain_name,extension").execute()


def get_signal_repository() -> SignalRepository:
    """Return the active signal repository."""
    if get_settings().supabase_enabled:
        return SupabaseSignalRepository()
    return LocalSignalRepository()
