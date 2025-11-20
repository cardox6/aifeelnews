"""
Google Cloud Secret Manager utilities for secure credential management.
"""

import logging
import os
from typing import Optional

from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class SecretManagerClient:
    """Client for accessing Google Cloud Secret Manager."""

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Secret Manager client.

        Args:
            project_id: GCP project ID. If None, will use environment or default.
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._client = None

    @property
    def client(self) -> secretmanager.SecretManagerServiceClient:
        """Lazy initialization of Secret Manager client."""
        if self._client is None:
            try:
                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Initialized Secret Manager client")
            except Exception as e:
                logger.warning(f"Failed to initialize Secret Manager client: {e}")
                raise
        return self._client

    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Get secret value from Secret Manager.

        Args:
            secret_name: Name of the secret
            version: Version of the secret (default: "latest")

        Returns:
            Secret value as string, or None if not found/accessible
        """
        if not self.project_id:
            logger.warning("No project ID available for Secret Manager")
            return None

        try:
            name = (
                f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            )
            response = self.client.access_secret_version(request={"name": name})
            secret_value: str = response.payload.data.decode("UTF-8")
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret_value
        except Exception as e:
            logger.warning(f"Failed to retrieve secret {secret_name}: {e}")
            return None


# Global instance
_secret_client = None


def get_secret_manager_client() -> SecretManagerClient:
    """Get or create global Secret Manager client instance."""
    global _secret_client
    if _secret_client is None:
        _secret_client = SecretManagerClient()
    return _secret_client


def get_secret_or_env(
    secret_name: str, env_var: str, default: Optional[str] = None
) -> Optional[str]:
    """
    Get value from Secret Manager, fallback to environment variable, then default.

    Args:
        secret_name: Secret Manager secret name
        env_var: Environment variable name
        default: Default value if neither source is available

    Returns:
        Secret/environment value or default
    """
    # Try Secret Manager first (production)
    try:
        client = get_secret_manager_client()
        secret_value = client.get_secret(secret_name)
        if secret_value:
            return secret_value
    except Exception:
        pass  # Fall back to environment variable

    # Fallback to environment variable (development)
    env_value = os.getenv(env_var)
    if env_value:
        return env_value

    # Return default
    return default
