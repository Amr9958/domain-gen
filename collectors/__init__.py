"""Signal collectors for external trend sources."""

from collectors.gnews import GNewsCollector
from collectors.github import GitHubCollector
from collectors.hackernews import HackerNewsCollector

__all__ = ["GNewsCollector", "GitHubCollector", "HackerNewsCollector"]
