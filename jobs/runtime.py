"""Minimal job runtime scaffolding for future scheduled tasks."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from core.logging import get_logger
from models import ProcessingRun


logger = get_logger("jobs.runtime")


@dataclass
class JobContext:
    """Lightweight execution context for collectors and processors."""

    run: ProcessingRun

    def complete(self, notes: str = "") -> ProcessingRun:
        """Mark the job as completed and log the outcome."""
        self.run = replace(
            self.run,
            status="completed",
            ended_at=datetime.utcnow(),
            notes=notes or self.run.notes,
        )
        logger.info("Job %s completed.", self.run.job_name)
        return self.run

    def fail(self, notes: str) -> ProcessingRun:
        """Mark the job as failed and log the outcome."""
        self.run = replace(
            self.run,
            status="failed",
            ended_at=datetime.utcnow(),
            notes=notes,
        )
        logger.error("Job %s failed: %s", self.run.job_name, notes)
        return self.run


def start_job(job_name: str, notes: str = "") -> JobContext:
    """Create and log a new processing run context."""
    run = ProcessingRun(
        job_name=job_name,
        run_id=uuid4().hex,
        started_at=datetime.utcnow(),
        status="running",
        notes=notes,
    )
    logger.info("Job %s started with run_id=%s", job_name, run.run_id)
    return JobContext(run=run)
