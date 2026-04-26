"""Database engine and session dependencies."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from domain_intel.core.settings import get_settings


settings = get_settings()

engine_options = {
    "echo": settings.database_echo,
    "pool_pre_ping": True,
    "future": True,
}
if not settings.database_url.startswith("sqlite"):
    engine_options.update(
        {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
        }
    )

engine = create_engine(settings.database_url, **engine_options)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
