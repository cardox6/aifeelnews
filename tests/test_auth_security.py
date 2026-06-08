"""Auth, OIDC, CORS and rate-limit assertions.

These tests prove that the security primitives shipped in Phases C and D
behave the way the threat model claims they do. They run against the real
FastAPI ``app`` via ``TestClient`` so the wiring (router include, middleware
order, dependency overrides) is exercised end-to-end.

Where a test depends on production semantics (e.g. OIDC enforcement only
fires when ``ENV == "production"``), the test reloads ``app.config`` and
``app.main`` under that environment and tears the override down at the
end so other tests are not contaminated.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _reload_app_with_env(env_value: str) -> Any:
    """Reload ``app.main`` (and the config singletons it depends on) under a
    specific ``ENV`` value so OIDC behaviour can be exercised in both modes.

    Returns the freshly imported app module so callers can grab ``.app``.
    """

    # Drop the cached modules so the new ENV is picked up at import time.
    for mod_name in [
        "app.main",
        "app.deps.oidc",
        "app.config",
        "app.config.security",
    ]:
        sys.modules.pop(mod_name, None)

    import os

    os.environ["ENV"] = env_value
    import app.config as _cfg  # noqa: F401 — force reload of singleton

    importlib.reload(_cfg)
    return importlib.import_module("app.main")


@pytest.fixture
def client() -> TestClient:
    """A TestClient bound to the default (``ENV=local``) app instance.

    We deliberately import ``app.main`` lazily so other tests that mutate
    the environment (via ``_reload_app_with_env``) do not poison this
    fixture.
    """

    from app.main import app

    return TestClient(app)


@pytest.fixture
def production_client() -> Iterator[TestClient]:
    """A TestClient backed by a freshly reloaded app with ENV=production.

    This is the only way to exercise the OIDC enforcement path because
    ``app/deps/oidc.py`` short-circuits in any non-production env.
    """

    import os

    original_env = os.environ.get("ENV")
    main_mod = _reload_app_with_env("production")
    try:
        yield TestClient(main_mod.app)
    finally:
        # Restore the original env and reload back to the default app so
        # later tests in the session see the same instance they expect.
        if original_env is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = original_env
        _reload_app_with_env(original_env or "local")


# -----------------------------------------------------------------------------
# Firebase-protected routes
# -----------------------------------------------------------------------------


class TestFirebaseAuthGate:
    """The bookmark routes use ``get_current_user`` — verify the gate."""

    def test_protected_route_requires_token(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.get("/bookmarks/")
        assert resp.status_code == 401
        assert "token" in resp.json()["detail"].lower()

    def test_protected_route_rejects_invalid_token(self, client: TestClient) -> None:
        """Bogus bearer → 401 (Firebase verification is mocked to fail)."""
        with patch(
            "app.deps.auth.verify_firebase_token",
            side_effect=Exception("invalid signature"),
        ):
            resp = client.get(
                "/bookmarks/",
                headers={"Authorization": "Bearer not-a-real-token"},
            )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_protected_route_rejects_malformed_header(self, client: TestClient) -> None:
        """Header without 'Bearer ' prefix → 401, never reaches Firebase."""
        resp = client.get(
            "/bookmarks/",
            headers={"Authorization": "totally-bogus"},
        )
        assert resp.status_code == 401


# -----------------------------------------------------------------------------
# Admin RBAC via Firebase custom claims
# -----------------------------------------------------------------------------


class TestAdminRbacGate:
    """``POST /sources/`` requires the signed ``role=admin`` custom claim.

    Authorization is sourced from the Firebase ID token (a transient
    ``user.role`` attribute set by ``get_current_user`` from the verified
    custom claim), NOT from any database column. ``GET /sources/`` stays
    public. Authentication (401) is enforced before authorization (403).
    """

    @staticmethod
    def _stub_user(role: str | None) -> Any:
        """A User with a transient ``.role`` — the field require_admin reads."""
        from app.models.user import User

        user = User(id=1, firebase_uid="u", email="u@x", hashed_password="")
        user.role = role  # type: ignore[attr-defined]
        return user

    @staticmethod
    def _override_db() -> Iterator[Any]:
        """A real generator get_db override. refresh() fills id + the two
        datetimes (DB server_defaults) so SourceRead serializes without a 500."""

        class _StubDb:
            def query(self, *_a: Any) -> Any:
                class _Q:
                    def filter(self, *_x: Any) -> "_Q":
                        return self

                    def filter_by(self, **_k: Any) -> "_Q":
                        return self

                    def first(self) -> None:
                        return None

                return _Q()

            def add(self, _obj: Any) -> None:
                pass

            def commit(self) -> None:
                pass

            def refresh(self, obj: Any) -> None:
                from datetime import datetime, timezone

                if getattr(obj, "id", None) is None:
                    obj.id = 1
                now = datetime.now(timezone.utc)
                obj.created_at = now
                obj.updated_at = now

        yield _StubDb()

    def test_non_admin_gets_403(self, client: TestClient) -> None:
        """A user without the admin claim → 403 (handler/DB never reached)."""
        from app.deps.auth import get_current_user
        from app.main import app as live_app

        live_app.dependency_overrides[get_current_user] = lambda: self._stub_user(None)
        try:
            resp = client.post("/sources/", json={"name": "BBC"})
        finally:
            live_app.dependency_overrides.pop(get_current_user, None)
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    def test_admin_role_claim_gets_through(self, client: TestClient) -> None:
        """A user with role=admin → 200; the gate opened and the source was
        created (against a stub session)."""
        from app.deps.auth import get_current_user
        from app.main import app as live_app
        from app.routers.sources import get_db as sources_get_db

        live_app.dependency_overrides[get_current_user] = lambda: self._stub_user(
            "admin"
        )
        live_app.dependency_overrides[sources_get_db] = self._override_db
        try:
            resp = client.post("/sources/", json={"name": "BBC"})
        finally:
            live_app.dependency_overrides.pop(get_current_user, None)
            live_app.dependency_overrides.pop(sources_get_db, None)
        assert resp.status_code == 200
        # SourceBase.validate_source_name lowercases the name.
        assert resp.json()["name"] == "bbc"

    def test_no_token_is_401_not_403(self, client: TestClient) -> None:
        """No Authorization header → 401 from get_current_user, before
        require_admin's 403 branch can run (authn precedes authz)."""
        resp = client.post("/sources/", json={"name": "BBC"})
        assert resp.status_code == 401

    def test_role_is_read_from_token_not_db(self, client: TestClient) -> None:
        """Exercise the REAL get_current_user: patch the verifier to return a
        decoded token carrying role=admin, with no DB role column anywhere.
        A 200 proves the privilege came from the signed claim."""
        from app.main import app as live_app
        from app.routers.sources import get_db as sources_get_db

        live_app.dependency_overrides[sources_get_db] = self._override_db
        try:
            with patch(
                "app.deps.auth.verify_firebase_token",
                return_value={"uid": "abc", "email": "a@x", "role": "admin"},
            ):
                resp = client.post(
                    "/sources/",
                    json={"name": "BBC"},
                    headers={"Authorization": "Bearer fake"},
                )
        finally:
            live_app.dependency_overrides.pop(sources_get_db, None)
        assert resp.status_code == 200
        assert resp.json()["name"] == "bbc"


# -----------------------------------------------------------------------------
# OIDC-protected scheduler endpoints
# -----------------------------------------------------------------------------


class TestSchedulerOidcGate:
    """``/api/v1/cleanup`` and ``/api/v1/trigger-ingestion`` require OIDC
    in production. In any other env the dep bypasses with a warning so
    pytest can keep running without GCP credentials."""

    def test_oidc_dependency_bypasses_in_local_env(self, client: TestClient) -> None:
        """ENV=local → bypass; the request reaches the handler.

        The handler itself can fail (no DB, no Mediastack key) but that's
        a 5xx, not a 401. We assert ``status_code != 401`` to prove the
        bypass works without coupling to whatever the handler does next.
        """
        resp = client.post("/api/v1/cleanup")
        assert resp.status_code != 401, (
            f"Expected OIDC bypass in local env, got 401: {resp.text}"
        )

    def test_oidc_dependency_rejects_missing_token(
        self, production_client: TestClient
    ) -> None:
        """ENV=production + no Authorization header → 401."""
        resp = production_client.post("/api/v1/cleanup")
        assert resp.status_code == 401
        assert "OIDC" in resp.json()["detail"] or "token" in resp.json()["detail"]

    def test_oidc_dependency_rejects_invalid_token(
        self, production_client: TestClient
    ) -> None:
        """ENV=production + malformed token → 401 (signature won't verify)."""
        resp = production_client.post(
            "/api/v1/cleanup",
            headers={"Authorization": "Bearer this.is.not.a.real.jwt"},
        )
        assert resp.status_code == 401

    def test_oidc_dependency_rejects_wrong_signer(
        self, production_client: TestClient
    ) -> None:
        """A correctly-signed token from the wrong service account → 401.

        We patch ``id_token.verify_oauth2_token`` to return claims that
        verify cryptographically but carry the wrong ``email`` claim.
        This proves the signer-allowlist check works independently of
        the cryptographic check.
        """
        with patch(
            "app.deps.oidc.id_token.verify_oauth2_token",
            return_value={
                "email": "attacker@evil.iam.gserviceaccount.com",
                "email_verified": True,
                "aud": "https://aifeelnews-web-813770885946.europe-west1.run.app",
            },
        ):
            resp = production_client.post(
                "/api/v1/cleanup",
                headers={"Authorization": "Bearer fake.but.cryptographically.valid"},
            )
        assert resp.status_code == 401
        assert "signer" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------


class TestCorsPolicy:
    """Verify that the CORS middleware refuses unknown origins."""

    def test_cors_accepts_known_origin(self, client: TestClient) -> None:
        """Firebase Hosting origin is in the allowlist."""
        resp = client.options(
            "/api/v1/sentiment/info",
            headers={
                "Origin": "https://aifeelnews-front.web.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert (
            resp.headers.get("access-control-allow-origin")
            == "https://aifeelnews-front.web.app"
        )

    def test_cors_rejects_unknown_origin(self, client: TestClient) -> None:
        """A preflight from evil.com must NOT receive Allow-Origin echo."""
        resp = client.options(
            "/api/v1/sentiment/info",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette's CORSMiddleware returns 400 for preflights it rejects
        # and crucially never sets `access-control-allow-origin`. Browsers
        # then refuse the cross-origin request.
        assert resp.headers.get("access-control-allow-origin") is None


# -----------------------------------------------------------------------------
# Rate limiting (slowapi)
# -----------------------------------------------------------------------------


class TestRateLimiting:
    """``slowapi`` returns 429 when the per-IP budget is blown."""

    def test_rate_limit_returns_429(self, client: TestClient) -> None:
        """Hit the sentiment info endpoint past its 60/minute budget.

        slowapi captures the limit string at decoration time, so we
        cannot lower the budget at runtime to make the test snappier
        — we just send 80 requests and assert at least one 429 surfaces.
        80 > 60 ensures the bucket is exhausted regardless of the small
        clock drift between requests.

        The limiter's in-memory storage is reset before and after so
        ordering with other tests is irrelevant.
        """
        from app.main import app as live_app

        live_app.state.limiter.reset()

        try:
            saw_429 = False
            for _ in range(80):
                resp = client.get("/api/v1/sentiment/info")
                if resp.status_code == 429:
                    saw_429 = True
                    break
            assert saw_429, (
                "Expected a 429 within 80 requests at 60/minute budget; "
                "limiter may not be wired correctly."
            )
        finally:
            live_app.state.limiter.reset()


# -----------------------------------------------------------------------------
# DB constraint → HTTP status translation
# -----------------------------------------------------------------------------


class TestBookmarkConflictHandling:
    """The ``trg_prevent_duplicate_bookmark`` PostgreSQL trigger raises
    ``IntegrityError`` on a duplicate ``(user_id, article_id)`` pair. The
    create-bookmark route must translate that into HTTP 409, not 500.

    The test runs against SQLite (which has no trigger), so we patch
    ``db.commit`` directly to raise ``IntegrityError``. That is the same
    exception class the route catches in production, so the test proves
    the catch + rollback + 409 path is wired correctly.
    """

    def test_create_bookmark_returns_409_on_integrity_error(
        self, client: TestClient
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        from app.deps.auth import get_current_user
        from app.main import app as live_app
        from app.models.user import User
        from app.routers.bookmarks import get_db as bookmarks_get_db

        # Stub out the auth dep so the request reaches the handler.
        fake_user = User(id=1, firebase_uid="test-uid", email="t@x", hashed_password="")

        class _StubDb:
            """Just enough Session surface to satisfy the route under test.

            ``commit`` raises IntegrityError once to simulate the trigger
            firing. ``rollback`` is recorded so the test can assert the
            handler called it before raising 409.
            """

            def __init__(self) -> None:
                self.rolled_back = False

            def add(self, _obj: Any) -> None:  # pragma: no cover — trivial
                pass

            def commit(self) -> None:
                raise IntegrityError("stmt", {}, Exception("duplicate"))

            def rollback(self) -> None:
                self.rolled_back = True

            def refresh(self, _obj: Any) -> None:  # pragma: no cover — unreachable
                pass

            def close(self) -> None:  # pragma: no cover — never called by client
                pass

        stub_db = _StubDb()

        def _override_get_db() -> Iterator[_StubDb]:
            yield stub_db

        def _override_get_current_user() -> User:
            return fake_user

        live_app.dependency_overrides[bookmarks_get_db] = _override_get_db
        live_app.dependency_overrides[get_current_user] = _override_get_current_user
        try:
            resp = client.post("/bookmarks/", json={"article_id": 42})
        finally:
            live_app.dependency_overrides.pop(bookmarks_get_db, None)
            live_app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()
        assert stub_db.rolled_back, (
            "create_bookmark must call db.rollback() before raising 409 — "
            "leaving the session in PendingRollbackError state breaks "
            "subsequent requests on the same connection."
        )


# -----------------------------------------------------------------------------
# Crawl-worker rollback hygiene
# -----------------------------------------------------------------------------


class TestCrawlWorkerRollbackHygiene:
    """Change B in the security PR: the crawl_worker exception handlers
    call ``db.rollback()`` BEFORE mutating ``crawl_job`` and re-committing.

    Without that rollback, a failed earlier commit leaves the session in
    ``PendingRollbackError`` and the second commit propagates, the job
    stays in its prior status, and the worker retries the poisoned job
    forever.

    The full ``crawl_article`` function has a wide mock surface (requests,
    robots, sentiment, NLP) that we don't want to recreate here. Instead
    we test the contract directly: after a network failure, the handler
    must record FAILED + ``NETWORK_ERROR`` and must have called rollback.
    """

    def test_network_error_handler_rolls_back_then_records_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests

        from app.jobs import crawl_worker
        from app.models.crawl_job import CrawlStatus

        # Make robots check return "allowed" without doing network IO.
        monkeypatch.setattr(
            crawl_worker,
            "check_robots_compliance",
            lambda _url: {"allowed": True, "reason": "ok"},
        )
        # Skip the rate-limit delay path.
        monkeypatch.setattr(crawl_worker, "respect_crawl_delay", lambda *_a: True)

        # Make the actual fetch raise RequestException so we land in the
        # handler under test.
        def _raise_network(*_a: Any, **_kw: Any) -> Any:
            raise requests.RequestException("simulated DNS failure")

        monkeypatch.setattr(crawl_worker.requests, "get", _raise_network)

        # Stub crawl_job + article. ``article`` is read once at the top
        # of the function for url + domain.
        class _Article:
            url = "https://example.com/post"

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

        crawl_job = _CrawlJob()

        # Stub Session: record the call sequence so we can assert order.
        calls: list[str] = []

        class _StubSession:
            def commit(self) -> None:
                calls.append("commit")

            def rollback(self) -> None:
                calls.append("rollback")

            # Methods the success path would touch but the failing path
            # below should never reach.
            def add(self, *_a: Any) -> None:  # pragma: no cover
                pass

            def query(self, *_a: Any) -> Any:  # pragma: no cover
                raise AssertionError("query() unexpected on network-error path")

        result = crawl_worker.crawl_article(crawl_job, _StubSession())  # type: ignore[arg-type]

        assert result is False
        assert crawl_job.status == CrawlStatus.FAILED
        assert crawl_job.error_code == "NETWORK_ERROR"
        assert "Network error" in crawl_job.error_message

        # The exact sequence we want: status-update commit (line ~140)
        # succeeded, then network error fired, then handler rolled back
        # before re-committing the failure record.
        assert calls == ["commit", "rollback", "commit"], (
            f"expected commit→rollback→commit, got {calls}"
        )


# -----------------------------------------------------------------------------
# Error semantics — generic 503 detail, no internal leak
# -----------------------------------------------------------------------------


class TestErrorDetailDoesNotLeakInternals:
    """The threat model (§1.I2) says 5xx responses must not leak the
    underlying exception text — connection strings, DB schema, stack
    frames. ``/health`` and ``/ready`` are the easiest surfaces to
    assert this on because both run a ``SELECT 1`` and surface a 503
    on failure.
    """

    def test_health_503_returns_generic_detail_when_db_unreachable(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sqlalchemy

        secret_token = "INTERNAL_DB_HOST_aifeelnews-prod:europe-west1"

        class _BoomSession:
            def execute(self, *_a: Any, **_kw: Any) -> Any:
                raise sqlalchemy.exc.OperationalError(
                    f"connection failed: {secret_token}", None, None
                )

            def close(self) -> None:
                pass

        # /health and /ready import SessionLocal lazily inside the handler,
        # so patching at the module attribute is what the handler actually
        # resolves.
        import app.database as database_mod

        monkeypatch.setattr(database_mod, "SessionLocal", _BoomSession)

        response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {"detail": "Service temporarily unavailable"}
        assert secret_token not in response.text

    def test_ready_503_returns_generic_detail_when_db_unreachable(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sqlalchemy

        secret_token = "INTERNAL_DB_HOST_aifeelnews-prod:europe-west1"

        class _BoomSession:
            def execute(self, *_a: Any, **_kw: Any) -> Any:
                raise sqlalchemy.exc.OperationalError(
                    f"connection failed: {secret_token}", None, None
                )

            def close(self) -> None:
                pass

        import app.database as database_mod

        monkeypatch.setattr(database_mod, "SessionLocal", _BoomSession)

        response = client.get("/ready")

        assert response.status_code == 503
        assert response.json() == {"detail": "Service temporarily unavailable"}
        assert secret_token not in response.text


class TestGlobalExceptionHandler:
    """An unhandled (non-HTTPException) error must surface as a generic 500
    with no internal detail, via the app-level Exception handler."""

    def test_unhandled_error_returns_generic_500(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app as live_app
        from app.routers.sources import get_db as sources_get_db

        secret = "INTERNAL_LEAK_db://prod-secret"

        def _boom_db() -> Any:
            raise RuntimeError(secret)
            yield  # pragma: no cover — unreachable, makes this a generator

        live_app.dependency_overrides[sources_get_db] = _boom_db
        # raise_server_exceptions=False lets the app's handler produce the
        # response instead of TestClient re-raising the exception.
        local_client = TestClient(live_app, raise_server_exceptions=False)
        try:
            resp = local_client.get("/sources/")
        finally:
            live_app.dependency_overrides.pop(sources_get_db, None)

        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal server error"}
        assert secret not in resp.text
