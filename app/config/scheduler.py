from pydantic_settings import BaseSettings, SettingsConfigDict


class SchedulerConfig(BaseSettings):
    """Configuration for Cloud Scheduler jobs optimized for API limits."""

    # Primary ingestion job - optimized for 10,000 requests/month
    ingestion_job_name: str = "aifeelnews-ingestion"
    ingestion_schedule: str = "0 */8 * * *"  # Every 8 hours (3x daily)
    ingestion_timezone: str = "UTC"

    # Cleanup job for expired content
    cleanup_job_name: str = "aifeelnews-cleanup"
    cleanup_schedule: str = "0 2 * * *"  # Daily at 2 AM UTC
    cleanup_timezone: str = "UTC"

    # GCP and service configuration
    scheduler_region: str = "europe-west1"
    service_url: str = "https://aifeelnews-web-813770885946.europe-west1.run.app"
    trigger_endpoint: str = "/api/v1/trigger-ingestion"

    # Job parameters (optimized for API limits)
    batch_size: int = 50  # API requests per ingestion run
    max_crawl_jobs: int = 100  # Articles to process per run

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def trigger_url(self) -> str:
        """Get the full trigger URL for Cloud Scheduler."""
        return f"{self.service_url}{self.trigger_endpoint}"

    @property
    def daily_articles_estimate(self) -> int:
        """Estimate daily articles based on scheduling."""
        runs_per_day = 3  # Every 8 hours
        articles_per_request = 25  # From IngestionConfig.mediastack_fetch_limit
        return runs_per_day * self.batch_size * articles_per_request

    @property
    def monthly_api_usage_estimate(self) -> int:
        """Estimate monthly API requests (should stay under 10,000)."""
        runs_per_day = 3
        days_per_month = 30.44
        return int(runs_per_day * self.batch_size * days_per_month)

    @property
    def api_usage_percentage(self) -> float:
        """Percentage of 10,000 monthly API limit."""
        return (self.monthly_api_usage_estimate / 10000) * 100
