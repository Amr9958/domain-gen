"""SQLAlchemy type helpers."""

from __future__ import annotations

from enum import Enum
from typing import Type

from sqlalchemy import Enum as SQLEnum


def enum_type(enum_class: Type[Enum], name: str) -> SQLEnum:
    """Create a PostgreSQL enum type that stores enum values, not names."""

    return SQLEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda values: [item.value for item in values],
    )
