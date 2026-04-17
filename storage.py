"""Portfolio persistence helpers with SQLite-first compatibility."""

from __future__ import annotations

import sqlite3

import pandas as pd

from constants import DB_PATH, PORTFOLIO_STATUS_UNCHECKED
from core.logging import get_logger
from repositories.portfolio import PortfolioEntry, get_portfolio_repository


logger = get_logger("storage")


CREATE_DOMAINS_TABLE_SQL = '''CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY,
    full_domain TEXT UNIQUE,
    name TEXT,
    ext TEXT,
    niche TEXT,
    appraisal_tier TEXT,
    appraisal_value TEXT,
    score INTEGER,
    scoring_profile TEXT,
    explanation TEXT,
    status TEXT,
    generated_date TEXT,
    purchased_date TEXT
)'''

EXPECTED_COLUMNS = {
    "full_domain": "TEXT UNIQUE",
    "name": "TEXT",
    "ext": "TEXT",
    "niche": "TEXT",
    "appraisal_tier": "TEXT",
    "appraisal_value": "TEXT",
    "score": "INTEGER",
    "scoring_profile": "TEXT",
    "explanation": "TEXT",
    "status": "TEXT",
    "generated_date": "TEXT",
    "purchased_date": "TEXT",
}


def _sync_portfolio_entry_to_cloud(entry: PortfolioEntry) -> None:
    """Mirror a local portfolio insert to Supabase when cloud mode is enabled."""
    cloud_repository = get_portfolio_repository(prefer_cloud=True)
    if cloud_repository.__class__.__name__ == "SupabasePortfolioRepository":
        synced = cloud_repository.add(entry)
        if synced:
            logger.info("Synced domain to Supabase portfolio: %s", entry.full_domain)
        else:
            logger.info("Supabase sync skipped or failed for: %s", entry.full_domain)

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection to the portfolio database."""
    return sqlite3.connect(db_path)


def init_db(db_path: str = DB_PATH) -> None:
    """Ensure the portfolio schema exists before the app renders."""
    with get_connection(db_path) as conn:
        conn.execute(CREATE_DOMAINS_TABLE_SQL)
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(domains)").fetchall()
        }
        for column_name, column_type in EXPECTED_COLUMNS.items():
            if column_name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE domains ADD COLUMN {column_name} {column_type}"
                )
        conn.commit()
    logger.info("SQLite portfolio database ready at %s", db_path)


def add_to_portfolio(
    full_domain: str,
    name: str,
    ext: str,
    niche: str,
    appraisal_tier: str,
    appraisal_value: str,
    score: int = 0,
    scoring_profile: str = "",
    explanation: str = "",
    status: str = PORTFOLIO_STATUS_UNCHECKED,
    db_path: str = DB_PATH,
) -> bool:
    """Insert a generated domain into the portfolio table.

    Returns `True` when the row is inserted and `False` when it already exists.
    """
    entry = PortfolioEntry.create(
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
    )
    inserted = get_portfolio_repository(prefer_cloud=False).add(entry)
    if inserted:
        logger.info("Added domain to portfolio: %s", full_domain)
        _sync_portfolio_entry_to_cloud(entry)
    else:
        logger.info("Skipped duplicate portfolio insert: %s", full_domain)
    return inserted


def get_portfolio(db_path: str = DB_PATH) -> pd.DataFrame:
    """Fetch the stored portfolio ordered by score and generation date."""
    _ = db_path
    return get_portfolio_repository(prefer_cloud=False).list_all()
