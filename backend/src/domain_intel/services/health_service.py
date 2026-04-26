"""Health-check service."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class HealthCheckResult:
    """Health status for the API and database dependency."""

    status: str
    database: str


class HealthService:
    """Run low-cost dependency checks."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def check(self) -> HealthCheckResult:
        """Return healthy or degraded status without leaking connection details."""

        try:
            self.session.execute(text("select 1"))
        except SQLAlchemyError:
            return HealthCheckResult(status="degraded", database="unavailable")
        return HealthCheckResult(status="ok", database="ok")
