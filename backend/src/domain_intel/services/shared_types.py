"""Shared service-layer value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MoneyValue:
    """API-safe money value using decimal strings."""

    amount: str
    currency: str
