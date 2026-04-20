"""Lazy exports for job entrypoints to avoid package-level import cycles."""

from __future__ import annotations

from typing import Any

from jobs.runtime import JobContext, start_job


def run_ingest_job(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load and run the ingest job on demand."""
    from jobs.ingest_signals import run_ingest_job as _run_ingest_job

    return _run_ingest_job(*args, **kwargs)


def run_processing_job(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load and run the processing job on demand."""
    from jobs.process_signals import run_processing_job as _run_processing_job

    return _run_processing_job(*args, **kwargs)


def run_domain_idea_job(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load and run the domain-idea job on demand."""
    from jobs.generate_domain_ideas import run_domain_idea_job as _run_domain_idea_job

    return _run_domain_idea_job(*args, **kwargs)


__all__ = ["JobContext", "run_domain_idea_job", "run_ingest_job", "run_processing_job", "start_job"]
