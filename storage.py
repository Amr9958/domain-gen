"""SQLite persistence helpers for the domain portfolio."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from constants import DB_PATH, PORTFOLIO_STATUS_UNCHECKED


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
    query = """INSERT INTO domains
        (full_domain, name, ext, niche, appraisal_tier, appraisal_value, score, scoring_profile, explanation, status, generated_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    values = (
        full_domain,
        name,
        ext,
        niche,
        appraisal_tier,
        appraisal_value,
        score,
        scoring_profile,
        explanation,
        status,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    try:
        with get_connection(db_path) as conn:
            conn.execute(query, values)
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_portfolio(db_path: str = DB_PATH) -> pd.DataFrame:
    """Fetch the stored portfolio ordered by score and generation date."""
    with get_connection(db_path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM domains ORDER BY score DESC, generated_date DESC",
            conn,
        )
