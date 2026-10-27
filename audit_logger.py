
import logging
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "file_activity.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
    force=True,
)


def log_action(action, source="", destination="", status="SUCCESS"):
    logging.info(
        "%s | Source: %s | Destination: %s | Status: %s",
        action, source, destination, status,
    )


def log_error(action, source, error):
    logging.error(
        "%s | Source: %s | Error: %s",
        action, source, error,
    )