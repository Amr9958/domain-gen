"""Phase 2 collection job: collect, clean, deduplicate, and cluster signals."""

from __future__ import annotations

from dataclasses import asdict

from collectors import GNewsCollector, GitHubCollector, HackerNewsCollector
from core.logging import configure_logging, get_logger
from jobs.runtime import start_job
from processors import clean_content_items, cluster_processed_items, deduplicate_content_items
from repositories.signals import get_signal_repository


logger = get_logger("jobs.collect_signals")


def run_collection_job() -> dict[str, int | str]:
    """Run the first end-to-end signal collection pipeline."""
    configure_logging()
    job = start_job("collect_signals", notes="Phase 2 initial collection pipeline")
    repository = get_signal_repository()
    collectors = [
        HackerNewsCollector(limit=20),
        GitHubCollector(limit=20),
        GNewsCollector(limit=20),
    ]

    try:
        raw_items = []
        for collector in collectors:
            raw_items.extend(collector.collect())

        cleaned_items = clean_content_items(raw_items)
        deduped_items = deduplicate_content_items(cleaned_items)
        clustered_items = cluster_processed_items(deduped_items)

        raw_rows = []
        for item in raw_items:
            row = asdict(item)
            row["tags"] = list(item.tags)
            raw_rows.append(row)

        repository.save_raw_items(raw_rows)
        repository.save_processed_items(clustered_items)
        repository.save_run(job)

        job.complete(
            notes=(
                f"Collected={len(raw_items)} cleaned={len(cleaned_items)} "
                f"deduped={len(deduped_items)} clustered={len(clustered_items)}"
            )
        )
        repository.save_run(job)

        summary = {
            "job_name": job.run.job_name,
            "run_id": job.run.run_id,
            "raw_items": len(raw_items),
            "deduped_items": len(deduped_items),
            "clustered_items": len(clustered_items),
            "status": job.run.status,
        }
        logger.info("Collection job finished: %s", summary)
        return summary
    except Exception as exc:
        job.fail(str(exc))
        repository.save_run(job)
        logger.exception("Collection job failed.")
        raise


if __name__ == "__main__":
    print(run_collection_job())
