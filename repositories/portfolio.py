"""Portfolio repository implementations for SQLite and optional Supabase."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol

import pandas as pd

from config import get_settings
from core.logging import get_logger
from integrations import get_supabase_manager


logger = get_logger("repositories.portfolio")


@dataclass(frozen=True)
class PortfolioEntry:
    """Stable portfolio row shape shared across storage backends."""

    full_domain: str
    name: str
    ext: str
    niche: str
    appraisal_tier: str
    appraisal_value: str
    score: int = 0
    scoring_profile: str = ""
    explanation: str = ""
    status: str = "Not checked"
    generated_date: str = ""
    purchased_date: str = ""

    @classmethod
    def create(
        cls,
        full_domain: str,
        name: str,
        ext: str,
        niche: str,
        appraisal_tier: str,
        appraisal_value: str,
        score: int = 0,
        scoring_profile: str = "",
        explanation: str = "",
        status: str = "Not checked",
    ) -> "PortfolioEntry":
        """Build a portfolio entry with a default timestamp."""
        return cls(
            full_domain=full_domain,
            name=name,
            ext=ext,
            niche=niche,
            appraisal_tier=appraisal_tier,
            appraisal_value=appraisal_value,
            score=score,
            scoring_profile=scoring_profile,
            explanation=explanation,
            status=status,
            generated_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )


class PortfolioRepository(Protocol):
    """Common contract for portfolio persistence."""

    def add(self, entry: PortfolioEntry) -> bool:
        """Insert a portfolio entry and return True when newly inserted."""

    def list_all(self) -> pd.DataFrame:
        """Return all portfolio rows in display-friendly order."""


class SqlitePortfolioRepository:
    """SQLite portfolio repository used by the current Streamlit app."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def add(self, entry: PortfolioEntry) -> bool:
        query = """INSERT INTO domains
            (full_domain, name, ext, niche, appraisal_tier, appraisal_value, score, scoring_profile, explanation, status, generated_date, purchased_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        values = (
            entry.full_domain,
            entry.name,
            entry.ext,
            entry.niche,
            entry.appraisal_tier,
            entry.appraisal_value,
            entry.score,
            entry.scoring_profile,
            entry.explanation,
            entry.status,
            entry.generated_date,
            entry.purchased_date or None,
        )
        try:
            with self._connect() as conn:
                conn.execute(query, values)
                conn.commit()
            logger.info("Added domain to SQLite portfolio: %s", entry.full_domain)
            return True
        except sqlite3.IntegrityError:
            logger.info("Skipped duplicate SQLite portfolio insert: %s", entry.full_domain)
            return False

    def list_all(self) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM domains ORDER BY score DESC, generated_date DESC",
                conn,
            )


class SupabasePortfolioRepository:
    """Optional cloud-backed portfolio repository."""

    def __init__(self) -> None:
        self.manager = get_supabase_manager()

    def add(self, entry: PortfolioEntry) -> bool:
        table = self.manager.table("portfolio_domains")
        if table is None:
            logger.info("Supabase portfolio insert skipped because client is unavailable.")
            return False

        payload = asdict(entry)
        try:
            response = table.upsert(payload, on_conflict="full_domain").execute()
            logger.info("Upserted domain into Supabase portfolio: %s", entry.full_domain)
            return bool(getattr(response, "data", None) is not None)
        except Exception as exc:  # pragma: no cover - network-backed path
            logger.warning("Supabase portfolio insert failed for %s: %s", entry.full_domain, exc)
            return False

    def list_all(self) -> pd.DataFrame:
        table = self.manager.table("portfolio_domains")
        if table is None:
            return pd.DataFrame()

        try:
            response = table.select("*").order("score", desc=True).order("generated_date", desc=True).execute()
            return pd.DataFrame(getattr(response, "data", []) or [])
        except Exception as exc:  # pragma: no cover - network-backed path
            logger.warning("Supabase portfolio fetch failed: %s", exc)
            return pd.DataFrame()


def get_portfolio_repository(prefer_cloud: bool = False) -> PortfolioRepository:
    """Return the appropriate portfolio repository for the current runtime."""
    settings = get_settings()
    if prefer_cloud and settings.supabase_enabled:
        return SupabasePortfolioRepository()
    return SqlitePortfolioRepository(str(settings.local_db_path))
