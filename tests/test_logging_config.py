"""Unit tests for shipping_tracker.logging_config.

Covers WR-03: configure_logging must be idempotent — repeated calls must not
accumulate handlers or open file descriptors on the root logger. No real network
or repo-level side effects (log_path is redirected into tmp_path).
"""

import logging
import logging.handlers
from pathlib import Path

from shipping_tracker.logging_config import configure_logging


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    """WR-03: two configure_logging() calls leave exactly one RotatingFileHandler
    on the root logger (no accumulation / fd leak)."""
    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    saved_level = root_logger.level
    log_path = str(tmp_path / "logs" / "t.log")

    try:
        configure_logging(log_path=log_path, log_level=logging.WARNING)
        configure_logging(log_path=log_path, log_level=logging.WARNING)

        rotating = [
            h
            for h in root_logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating) == 1
        assert root_logger.level == logging.WARNING
    finally:
        # Restore root logger to its pre-test state so we don't pollute the suite
        # (the fix closes existing handlers, including pytest/caplog handlers).
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)
            h.close()
        for h in saved_handlers:
            root_logger.addHandler(h)
        root_logger.setLevel(saved_level)
