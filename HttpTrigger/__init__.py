import logging
import json
from pathlib import Path
import sys

import azure.functions as func

# Ensure project root is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import app  # type: ignore
except Exception as exc:
    logging.error("Failed to import app.py: %s", exc, exc_info=True)
    raise


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger received for daily scrape test')
    try:
        app.scrape_turkish_ecommerce_sites()
        body = {"success": True, "message": "Scrape completed (invoked via HTTP trigger)."}
        return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")
    except Exception as e:
        logging.exception("Scrape failed:")
        body = {"success": False, "message": str(e)}
        return func.HttpResponse(json.dumps(body), status_code=500, mimetype="application/json")
