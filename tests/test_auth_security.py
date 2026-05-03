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
