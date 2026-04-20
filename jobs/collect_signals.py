"""Compatibility wrapper that runs Phase 2 ingestion then processing."""

from __future__ import annotations

from core.logging import configure_logging, get_logger
from jobs.generate_domain_ideas import run_domain_idea_job
from jobs.ingest_signals import run_ingest_job
from jobs.process_signals import run_processing_job


logger = get_logger("jobs.collect_signals")


def run_collection_job() -> dict[str, int | str]:
    """Run the combined ingest/process/domain-ideas pipeline without breaking old entrypoints."""
    configure_logging()
    ingest_summary = run_ingest_job()
    process_summary = run_processing_job()
    ideas_summary = run_domain_idea_job()
    summary = {
        "job_name": "collect_signals",
        "status": ideas_summary["status"],
        "raw_items": int(ingest_summary.get("raw_items", 0)),
        "processed_items": int(process_summary.get("processed_items", 0)),
        "themes": int(process_summary.get("themes", 0)),
        "keywords": int(process_summary.get("keywords", 0)),
        "domain_ideas": int(ideas_summary.get("domain_ideas", 0)),
        "shortlist": int(ideas_summary.get("shortlist", 0)),
        "watchlist": int(ideas_summary.get("watchlist", 0)),
        "rejected": int(ideas_summary.get("rejected", 0)),
    }
    logger.info("Combined collection job finished: %s", summary)
    return summary


if __name__ == "__main__":
    print(run_collection_job())
