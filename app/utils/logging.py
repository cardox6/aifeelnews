"""Structured JSON logging compatible with Google Cloud Logging.

Uses JSON in production (auto-parsed by Cloud Logging) and plain text locally.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class CloudJsonFormatter(logging.Formatter):
    """Format log records as JSON that Cloud Logging auto-parses."""

    SEVERITY_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "severity": self.SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "module": record.module,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure application-wide logging.

    JSON in production (Cloud Logging), plain text locally (readability).
    """
    env = os.getenv("ENV", "development")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if env in ("production", "prod"):
        handler.setFormatter(CloudJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )

    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
