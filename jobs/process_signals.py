"""Phase 2 processing job for cleaning, clustering, classification, themes, and keywords."""

from __future__ import annotations

from core.logging import configure_logging, get_logger
from jobs.runtime import start_job
from processors import (
    build_themes,
    classify_clustered_items,
    clean_content_items,
    cluster_processed_items,
    deduplicate_content_items,
    extract_keyword_insights,
)
from repositories.signals import get_signal_repository


logger = get_logger("jobs.process_signals")


def run_processing_job() -> dict[str, int | str]:
    """Process unprocessed raw signals into classified theme and keyword intelligence rows."""
    configure_logging()
    job = start_job("process_signals", notes="Phase 2 processing pipeline")
    repository = get_signal_repository()
    repository.save_run(job)

    try:
        raw_items = repository.list_raw_items(only_unprocessed=True)
        if not raw_items:
            job.complete(notes="No unprocessed raw items found.")
            repository.save_run(job)
            summary = {
                "job_name": job.run.job_name,
                "run_id": job.run.run_id,
                "raw_items": 0,
                "processed_items": 0,
                "themes": 0,
                "keywords": 0,
                "status": job.run.status,
            }
            logger.info("Processing job finished with no work: %s", summary)
            return summary

        existing_themes = repository.list_themes()
        cleaned_items = clean_content_items(raw_items)
        deduped_items = deduplicate_content_items(cleaned_items)
        clustered_items = cluster_processed_items(deduped_items)
        classified_items = classify_clustered_items(clustered_items)
        processed_items, themes = build_themes(classified_items, existing_themes=existing_themes)
        keyword_insights = extract_keyword_insights(processed_items, themes)

        repository.save_processed_items(processed_items, run_id=job.run.run_id)
        repository.save_themes(themes)
        repository.save_keywords(keyword_insights)

        job.complete(
            notes=(
                f"Raw={len(raw_items)} cleaned={len(cleaned_items)} deduped={len(deduped_items)} "
                f"processed={len(processed_items)} themes={len(themes)} keywords={len(keyword_insights)}"
            )
        )
        repository.save_run(job)

        summary = {
            "job_name": job.run.job_name,
            "run_id": job.run.run_id,
            "raw_items": len(raw_items),
            "deduped_items": len(deduped_items),
            "processed_items": len(processed_items),
            "themes": len(themes),
            "keywords": len(keyword_insights),
            "status": job.run.status,
        }
        logger.info("Processing job finished: %s", summary)
        return summary
    except Exception as exc:
        job.fail(str(exc))
        repository.save_run(job)
        logger.exception("Processing job failed.")
        raise


if __name__ == "__main__":
    print(run_processing_job())
