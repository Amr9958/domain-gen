"""Generate scored domain opportunities from keyword insights."""

from __future__ import annotations

from collections import Counter

from core.logging import configure_logging, get_logger
from jobs.runtime import start_job
from processors import generate_domain_opportunities
from repositories.signals import get_signal_repository


logger = get_logger("jobs.generate_domain_ideas")


def run_domain_idea_job() -> dict[str, int | str]:
    """Build domain ideas from stored themes and keyword insights."""
    configure_logging()
    job = start_job("generate_domain_ideas", notes="Generate scored domain opportunities")
    repository = get_signal_repository()
    repository.save_run(job)

    try:
        themes = repository.list_themes()
        keywords = repository.list_keywords()
        if not themes or not keywords:
            job.complete(notes="No themes or keyword insights found.")
            repository.save_run(job)
            summary = {
                "job_name": job.run.job_name,
                "run_id": job.run.run_id,
                "themes": len(themes),
                "keywords": len(keywords),
                "domain_ideas": 0,
                "status": job.run.status,
            }
            logger.info("Domain idea job finished with no work: %s", summary)
            return summary

        domain_ideas = generate_domain_opportunities(keywords, themes)
        repository.save_domain_ideas(domain_ideas)
        recommendation_counts = Counter(opportunity.recommendation.value for opportunity in domain_ideas)
        review_bucket_counts = Counter(opportunity.review_bucket for opportunity in domain_ideas)

        job.complete(
            notes=(
                f"Themes={len(themes)} keywords={len(keywords)} domain_ideas={len(domain_ideas)} "
                f"buy={recommendation_counts.get('buy', 0)} watch={recommendation_counts.get('watch', 0)} "
                f"skip={recommendation_counts.get('skip', 0)} shortlist={review_bucket_counts.get('shortlist', 0)} "
                f"watchlist={review_bucket_counts.get('watchlist', 0)} rejected={review_bucket_counts.get('rejected', 0)}"
            )
        )
        repository.save_run(job)

        summary = {
            "job_name": job.run.job_name,
            "run_id": job.run.run_id,
            "themes": len(themes),
            "keywords": len(keywords),
            "domain_ideas": len(domain_ideas),
            "buy": recommendation_counts.get("buy", 0),
            "watch": recommendation_counts.get("watch", 0),
            "skip": recommendation_counts.get("skip", 0),
            "shortlist": review_bucket_counts.get("shortlist", 0),
            "watchlist": review_bucket_counts.get("watchlist", 0),
            "rejected": review_bucket_counts.get("rejected", 0),
            "status": job.run.status,
        }
        logger.info("Domain idea job finished: %s", summary)
        return summary
    except Exception as exc:
        job.fail(str(exc))
        repository.save_run(job)
        logger.exception("Domain idea job failed.")
        raise


if __name__ == "__main__":
    print(run_domain_idea_job())
