import json
import logging
from pathlib import Path

from orders_ingest.cleaning import read_orders, write_clean, write_reject

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    logger.info("run started")

    config = load_config(PROJECT_ROOT / "config.json")
    input_path = PROJECT_ROOT / config["input_path"]
    clean_path = PROJECT_ROOT / config["clean_output_path"]
    rejects_path = PROJECT_ROOT / config["rejects_output_path"]

    clean, rejects, read_count = read_orders(input_path)
    logger.info(
        "read %s rows: %s clean, %s rejected", read_count, len(clean), len(rejects)
    )

    if rejects:
        logger.warning("%s rows rejected, see %s", len(rejects), rejects_path)

    written = write_clean(clean, clean_path)
    logger.info("wrote %s rows to %s", written, clean_path)

    rejected = write_reject(rejects, rejects_path)
    logger.info("wrote %s rejects to %s", rejected, rejects_path)

    logger.info("run finished")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("run failed")
        raise
