"""Phase 2 raw ingestion job for external signal collection."""

from __future__ import annotations

from collectors import GNewsCollector, GitHubCollector, HackerNewsCollector
from core.logging import configure_logging, get_logger
from jobs.runtime import start_job
from repositories.signals import get_signal_repository


logger = get_logger("jobs.ingest_signals")


def run_ingest_job() -> dict[str, int | str]:
    """Collect raw items from external sources and persist them without processing."""
    configure_logging()
    job = start_job("ingest_signals", notes="Phase 2 raw signal ingestion")
    repository = get_signal_repository()
    repository.save_run(job)
    collectors = [
        HackerNewsCollector(limit=20),
        GitHubCollector(limit=20),
        GNewsCollector(limit=20),
    ]

    try:
        raw_items = []
        for collector in collectors:
            raw_items.extend(collector.collect())

        repository.save_raw_items(raw_items, run_id=job.run.run_id)
        job.complete(notes=f"Ingested={len(raw_items)} raw items")
        repository.save_run(job)

        summary = {
            "job_name": job.run.job_name,
            "run_id": job.run.run_id,
            "raw_items": len(raw_items),
            "status": job.run.status,
        }
        logger.info("Ingestion job finished: %s", summary)
        return summary
    except Exception as exc:
        job.fail(str(exc))
        repository.save_run(job)
        logger.exception("Ingestion job failed.")
        raise


if __name__ == "__main__":
    print(run_ingest_job())
