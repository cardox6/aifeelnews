"""OIDC token verification for Cloud Scheduler-triggered endpoints.

Cloud Scheduler can attach a Google-signed OIDC ID token to outbound
HTTP requests when a job is configured with ``oidc_token``. The token's
``aud`` claim is the configured audience (we use the Cloud Run service
URL) and the token's ``email`` claim is the service account that signed
it.

This module provides a FastAPI dependency that extracts the bearer
token, verifies its signature against Google's public keys, and asserts
both the audience and the signing service account match what we expect
in production. In any non-production environment the dependency logs a
warning and lets the request through so ``pytest`` and local
``uvicorn`` runs do not require a real GCP token.

Reference:
- https://cloud.google.com/run/docs/triggering/using-scheduler#authentication
- https://google-auth.readthedocs.io/en/master/reference/google.oauth2.id_token.html
"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import config

logger = logging.getLogger(__name__)


def _bypass_for_non_production() -> bool:
    """Return True if OIDC verification should be skipped in this env.

    Verification is skipped for any ``ENV`` other than ``production``.
    A warning is logged the first time per request so the bypass is
    visible in test output and local dev logs but not silent.
    """

    # Fail closed: only a known dev/CI env bypasses OIDC. Production OR any
    # unrecognized ENV enforces it, so a one-character ENV drift can't silently
    # disable auth on the scheduler endpoints.
    if not config.security.oidc_bypass_allowed:
        return False
    logger.warning(
        "OIDC verification bypassed (ENV=%s). This must never happen in production.",
        config.security.env,
    )
    return True


def verify_scheduler_oidc(
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """FastAPI dependency that verifies a Cloud Scheduler OIDC token.

    Behaviour:
    - In non-production environments, returns a stub claims dict and
      logs a warning. This keeps unit tests and local development
      runnable without GCP credentials.
    - In production, requires an ``Authorization: Bearer <token>``
      header. The token is verified against the configured audience
      (the Cloud Run service URL) using ``google-auth``. The signing
      service account email must match
      ``config.security.scheduler_service_account``.
    - Any failure (missing header, malformed token, bad signature,
      wrong audience, wrong signer) raises ``HTTPException(401)`` with
      a non-leaky message.

    Returns:
        The verified token claims dict on success. Routes that don't
        need the claims can ignore the return value; the dependency's
        side effect is the 401 raised on failure.
    """

    if _bypass_for_non_production():
        return {"sub": "local-dev", "email": "local-dev@example.com"}

    if not authorization or not authorization.startswith("Bearer "):
        # 401 over 403 because the request never produced a valid
        # credential — auth is missing, not insufficient.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing OIDC bearer token",
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty OIDC bearer token",
        )

    expected_audience = config.security.cloud_run_url
    expected_service_account = config.security.scheduler_service_account

    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=expected_audience,
        )
    except ValueError as exc:
        # google-auth raises ValueError for any verification failure
        # (expired, bad signature, wrong audience). We log the cause
        # but only return a generic message to the caller.
        logger.warning("OIDC token rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC token",
        ) from exc

    signer_email = claims.get("email", "")
    if signer_email != expected_service_account:
        logger.warning(
            "OIDC token signer %s does not match expected %s",
            signer_email,
            expected_service_account,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted OIDC token signer",
        )

    if not claims.get("email_verified", False):
        logger.warning("OIDC token signer email not verified: %s", signer_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token signer email not verified",
        )

    return dict(claims)
