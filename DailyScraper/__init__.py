import datetime
import logging
import os
import sys
from pathlib import Path

import azure.functions as func


# Ensure app.py (project root) is importable when running in Azure Functions
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import app  # type: ignore
except Exception as exc:  # pragma: no cover
    logging.error("Failed to import app.py: %s", exc, exc_info=True)
    raise


def main(mytimer: func.TimerRequest) -> None:
    """Timer trigger entrypoint: runs daily scrape and Azure Table write."""
    utc_now = datetime.datetime.utcnow().isoformat()
    logging.info("DailyScraper triggered at %s", utc_now)

    try:
        app.scrape_turkish_ecommerce_sites()
        logging.info("DailyScraper completed successfully")
    except Exception as exc:  # pragma: no cover
        logging.exception("DailyScraper failed: %s", exc)
        raise
