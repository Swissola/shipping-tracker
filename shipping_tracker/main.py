"""Pipeline orchestrator — stub for Phase 1."""

import logging

from dotenv import load_dotenv

from shipping_tracker.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the shipping-tracker pipeline.

    Returns:
        0 on success, non-zero on unrecoverable error.

    Phase 1 stub: loads environment, configures logging, and returns 0.
    Phases 2–5 wire in Gmail fetch, email parsing, deduplication, and
    TrackingMore registration without changing this function's signature.
    """
    load_dotenv()
    configure_logging()

    logger.warning("shipping_tracker started — pipeline stub, no work performed")
    return 0
