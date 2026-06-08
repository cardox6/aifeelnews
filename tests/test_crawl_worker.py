"""Branch tests for crawl_worker.crawl_article.

The previous file of this name contained a manual real-HTTP smoke script with
zero collectable pytest tests (moved to scripts/dev/manual_crawl_smoke.py).
These mock the network + robots layer and assert the early-return branches that
the live worker depends on: a robots.txt block and an active rate-limit must
each park the job in the right terminal status without fetching. The
network-error rollback path is covered in
test_auth_security.py::TestCrawlWorkerRollbackHygiene.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.jobs import crawl_worker
from app.models.crawl_job import CrawlStatus


class _Article:
    url = "https://example.com/post"


def _crawl_job() -> Any:
    class _CrawlJob:
        article = _Article()
        status: Any = CrawlStatus.PENDING
        error_code: Any = None
        error_message: Any = None
        updated_at: Any = None
        robots_allowed: Any = None
        http_status: Any = None
        bytes_downloaded: Any = None
        fetched_at: Any = None

    return _CrawlJob()


class _StubSession:
    """Records commit/rollback; fails loudly if the fetch path is reached."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def commit(self) -> None:
        self.calls.append("commit")

    def rollback(self) -> None:  # pragma: no cover - not expected on these paths
        self.calls.append("rollback")

    def add(self, *_a: Any) -> None:  # pragma: no cover
        raise AssertionError("add() should not be reached on an early-return branch")


def test_robots_block_parks_job_forbidden_without_fetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """robots.txt disallow → FORBIDDEN_BY_ROBOTS, and requests.get is never
    called (we make it explode to prove the early return)."""
    monkeypatch.setattr(
        crawl_worker,
        "check_robots_compliance",
        lambda _url: {"allowed": False, "reason": "Disallowed by robots.txt"},
    )

    def _boom_get(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError("requests.get must not run when robots disallows")

    monkeypatch.setattr(crawl_worker.requests, "get", _boom_get)

    job = _crawl_job()
    session = _StubSession()
    result = crawl_worker.crawl_article(job, session)  # type: ignore[arg-type]

    assert result is False
    assert job.status == CrawlStatus.FORBIDDEN_BY_ROBOTS
    assert job.robots_allowed is False
    assert "robots" in job.error_message.lower()


def test_rate_limited_parks_job_without_fetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """robots allows but the crawl-delay isn't satisfied → RATE_LIMITED, and
    again no fetch happens."""
    monkeypatch.setattr(
        crawl_worker,
        "check_robots_compliance",
        lambda _url: {"allowed": True, "reason": "ok"},
    )
    # respect_crawl_delay returning False means "too soon, back off".
    monkeypatch.setattr(crawl_worker, "respect_crawl_delay", lambda *_a: False)

    def _boom_get(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError("requests.get must not run when rate-limited")

    monkeypatch.setattr(crawl_worker.requests, "get", _boom_get)

    job = _crawl_job()
    session = _StubSession()
    result = crawl_worker.crawl_article(job, session)  # type: ignore[arg-type]

    assert result is False
    assert job.status == CrawlStatus.RATE_LIMITED
    assert "rate limited" in job.error_message.lower()


def test_create_crawl_jobs_picks_newest_articles_first(test_db: Any) -> None:
    """Regression: create_crawl_jobs_for_articles must enqueue the NEWEST
    un-crawled articles (published_at DESC). The bug was an unordered query +
    a 20-job cap, which starved freshly-ingested articles behind old backlog so
    the latest articles never reached GCP NL. Here 5 articles span 5 days and we
    create only 3 jobs — they must be the 3 newest, not an arbitrary slice."""
    from datetime import datetime, timedelta, timezone

    from app.models.article import Article
    from app.models.crawl_job import CrawlJob
    from app.models.source import Source

    test_db.add(Source(id=1, name="bbc"))
    test_db.flush()
    base = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    # Insert oldest-first so insertion order is the OPPOSITE of published order —
    # an unordered query would tend to return the oldest, failing this test.
    for i in range(5):
        test_db.add(
            Article(
                source_id=1,
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                published_at=base + timedelta(days=i),  # i=4 is newest
            )
        )
    test_db.commit()

    created = crawl_worker.create_crawl_jobs_for_articles(test_db, limit=3)
    assert created == 3

    # The 3 jobs must be for the 3 newest articles (published days 4, 3, 2).
    job_article_ids = {cj.article_id for cj in test_db.query(CrawlJob).all()}
    newest_three = {
        a.id
        for a in test_db.query(Article)
        .order_by(Article.published_at.desc())
        .limit(3)
        .all()
    }
    assert job_article_ids == newest_three
