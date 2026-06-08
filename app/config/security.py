"""Security-related runtime configuration.

Centralises the inputs needed for OIDC token verification on Cloud
Scheduler endpoints and for the slowapi rate limiter. Kept as a separate
Pydantic settings module so other concerns (database, ingestion) remain
unaware of security wiring.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityConfig(BaseSettings):
    """Security configuration loaded from environment variables.

    Notes on defaults:
    - ``cloud_run_url`` defaults to the production service URL so OIDC
      audience verification works out of the box on Cloud Run. Override
      with the ``CLOUD_RUN_URL`` env var for staging or a different
      project.
    - ``scheduler_service_account`` is the email of the GCP service
      account Cloud Scheduler is configured with (see ``infra/main.tf``
      ``oidc_token`` block). If a token is signed by any other service
      account, OIDC verification will reject it.
    - ``env`` mirrors the global ``ENV`` variable. When it is anything
      other than ``production`` the OIDC dependency bypasses verification
      with a logged warning so local development against ``uvicorn`` and
      the test suite continue to work.
    """

    env: str = Field(default="local", alias="ENV")
    cloud_run_url: str = Field(
        default="https://aifeelnews-web-813770885946.europe-west1.run.app",
        alias="CLOUD_RUN_URL",
    )
    scheduler_service_account: str = Field(
        default="cloudrun-sa@aifeelnews-prod.iam.gserviceaccount.com",
        alias="SCHEDULER_SERVICE_ACCOUNT",
    )

    # Rate limit defaults — overridable per-environment without code change
    rate_limit_analytics: str = Field(default="30/minute", alias="RATE_LIMIT_ANALYTICS")
    rate_limit_sentiment: str = Field(default="60/minute", alias="RATE_LIMIT_SENTIMENT")
    rate_limit_scheduler: str = Field(default="6/hour", alias="RATE_LIMIT_SCHEDULER")
    rate_limit_metrics: str = Field(default="60/minute", alias="RATE_LIMIT_METRICS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The canonical "this is production" value set. Accepts both spellings so a
    # single ENV source (e.g. Terraform's environment="prod") can't silently
    # flip is_production to False and disable OIDC on the scheduler endpoints.
    _PRODUCTION_ENVS = frozenset({"production", "prod"})
    # Envs where it is safe to bypass OIDC (local dev / CI). Anything NOT in
    # this set and NOT production is treated as production for auth purposes —
    # fail closed, so an unrecognized ENV enforces OIDC rather than skipping it.
    _OIDC_BYPASS_ENVS = frozenset({"local", "test", "development", "dev"})

    @property
    def is_production(self) -> bool:
        return self.env in self._PRODUCTION_ENVS

    @property
    def oidc_bypass_allowed(self) -> bool:
        """Whether OIDC verification may be skipped for the current ENV.

        Fail-closed: only an explicitly-known dev/CI env bypasses; any value
        that is production OR unrecognized enforces OIDC.
        """
        return self.env in self._OIDC_BYPASS_ENVS
