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


def test_skips_gcp_nl_reanalysis_when_already_analyzed(
    test_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a re-processed crawl job must NOT re-run GCP NL on an article
    that already has a GCP_NL analysis.

    GCP NL annotateText is the metered cost (free-tier ~5k units/month). Without
    a guard, a retried job (e.g. a RATE_LIMITED attempt that later succeeds)
    re-called the API and inserted a *duplicate* SentimentAnalysis row — in prod
    this reached 20+ analyses for a single article, a ~6.6x budget waste that
    starved magnitude coverage. The guard skips the call and marks the job
    SUCCESS, keeping the existing analysis.
    """
    from datetime import datetime, timezone

    from app.models.article import Article
    from app.models.crawl_job import CrawlJob, CrawlStatus
    from app.models.sentiment_analysis import SentimentAnalysis
    from app.models.source import Source

    monkeypatch.setenv("SENTIMENT_PROVIDER", "GCP_NL")

    test_db.add(Source(id=1, name="bbc"))
    test_db.flush()
    article = Article(
        source_id=1,
        title="Already analyzed",
        url="https://example.com/analyzed",
        published_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )
    test_db.add(article)
    test_db.flush()
    # Pre-existing GCP_NL analysis (as if a prior crawl already ran it).
    test_db.add(
        SentimentAnalysis(
            article_id=article.id,
            provider="GCP_NL",
            model_name="gcp_nl_v1",
            score=0.5,
            magnitude=9.2,
            label="positive",
            language="en",
        )
    )
    job = CrawlJob(article_id=article.id, status=CrawlStatus.PENDING)
    test_db.add(job)
    test_db.commit()

    # Reach the analysis block: robots OK, delay OK, fetch + extract stubbed.
    monkeypatch.setattr(
        crawl_worker, "check_robots_compliance", lambda _url: {"allowed": True}
    )
    monkeypatch.setattr(crawl_worker, "respect_crawl_delay", lambda *_a: True)

    class _Resp:
        status_code = 200
        text = "<html><body>some fresh body text</body></html>"
        content = b"x" * 100

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr(crawl_worker.requests, "get", lambda *_a, **_kw: _Resp())
    monkeypatch.setattr(
        crawl_worker, "extract_article_text", lambda *_a, **_kw: "fresh body text"
    )

    # The guard must prevent this from ever being called. crawl_article imports
    # annotate_text_gcp_nl *locally* from app.utils.sentiment, so patch it at the
    # source module (patching crawl_worker.* would not intercept the local import)
    # — this makes the test fail loudly if the guard is ever removed.
    def _boom_gcp(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError(
            "annotate_text_gcp_nl must NOT run for an already-GCP_NL-analyzed article"
        )

    import app.utils.sentiment as _sentiment_mod

    monkeypatch.setattr(_sentiment_mod, "annotate_text_gcp_nl", _boom_gcp)

    result = crawl_worker.crawl_article(job, test_db)

    assert result is True
    assert job.status == CrawlStatus.SUCCESS
    # Still exactly ONE GCP_NL analysis — no duplicate inserted.
    assert (
        test_db.query(SentimentAnalysis)
        .filter_by(article_id=article.id, provider="GCP_NL")
        .count()
        == 1
    )
