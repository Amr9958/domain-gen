"""Scoring data structures and typing contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True)
class HardFilterResult:
    """Outcome of pre-scoring quality and trust checks."""

    reject: bool = False
    score_cap: int | None = None
    penalty: int = 0
    flags: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainAppraisal:
    """Structured appraisal output for a candidate domain name."""

    domain: str
    name: str
    tld: str
    profile: str
    final_score: int
    grade: str
    tier: str
    value: str
    subscores: Mapping[str, int]
    flags: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    explanation: str = ""
    rejected: bool = False


class DomainScorer(Protocol):
    """Protocol for pluggable scoring engines."""

    def evaluate_domain(
        self,
        domain: str,
        profile: str = "startup_brand",
        niche: str = "",
        word_banks: Mapping[str, Sequence[str]] | None = None,
    ) -> DomainAppraisal:
        """Return a full appraisal for a candidate domain."""
