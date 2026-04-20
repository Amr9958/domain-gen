"""Tests for lightweight job wrappers and no-work flows."""

from __future__ import annotations

from datetime import datetime
import unittest
from unittest.mock import patch

from jobs.collect_signals import run_collection_job
from jobs.process_signals import run_processing_job
from jobs.runtime import JobContext
from models import ProcessingRun


class _FakeRepository:
    def __init__(self) -> None:
        self.saved_runs: list[str] = []

    def save_run(self, job: JobContext) -> None:
        self.saved_runs.append(job.run.status)

    def list_raw_items(self, *, only_unprocessed: bool = False) -> list[object]:
        _ = only_unprocessed
        return []


def _fake_job_context(job_name: str, notes: str = "") -> JobContext:
    return JobContext(
        run=ProcessingRun(
            job_name=job_name,
            run_id=f"{job_name}-run",
            started_at=datetime.utcnow(),
            status="running",
            notes=notes,
        )
    )


class JobTests(unittest.TestCase):
    @patch("jobs.collect_signals.configure_logging")
    @patch("jobs.collect_signals.run_domain_idea_job")
    @patch("jobs.collect_signals.run_processing_job")
    @patch("jobs.collect_signals.run_ingest_job")
    def test_collect_signals_wrapper_combines_subjob_summaries(
        self,
        mocked_ingest_job,
        mocked_processing_job,
        mocked_domain_idea_job,
        mocked_configure_logging,
    ) -> None:
        mocked_ingest_job.return_value = {"raw_items": 6}
        mocked_processing_job.return_value = {"processed_items": 4, "themes": 2, "keywords": 5}
        mocked_domain_idea_job.return_value = {
            "status": "completed",
            "domain_ideas": 7,
            "shortlist": 2,
            "watchlist": 3,
            "rejected": 2,
        }

        summary = run_collection_job()

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["raw_items"], 6)
        self.assertEqual(summary["processed_items"], 4)
        self.assertEqual(summary["domain_ideas"], 7)
        mocked_configure_logging.assert_called_once()

    @patch("jobs.process_signals.configure_logging")
    @patch("jobs.process_signals.get_signal_repository")
    @patch("jobs.process_signals.start_job")
    def test_processing_job_returns_completed_zero_summary_when_no_raw_items(
        self,
        mocked_start_job,
        mocked_get_signal_repository,
        mocked_configure_logging,
    ) -> None:
        repository = _FakeRepository()
        mocked_get_signal_repository.return_value = repository
        mocked_start_job.return_value = _fake_job_context("process_signals", "Phase 2 processing pipeline")

        summary = run_processing_job()

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["raw_items"], 0)
        self.assertEqual(summary["processed_items"], 0)
        self.assertEqual(summary["themes"], 0)
        self.assertEqual(summary["keywords"], 0)
        self.assertGreaterEqual(len(repository.saved_runs), 2)
        mocked_configure_logging.assert_called_once()


if __name__ == "__main__":
    unittest.main()
