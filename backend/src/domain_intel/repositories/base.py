"""Base repository primitives."""

from __future__ import annotations

from sqlalchemy.orm import Session


class BaseRepository:
    """Small wrapper around a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self.session = session
