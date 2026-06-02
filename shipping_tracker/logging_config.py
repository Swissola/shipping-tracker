"""Logging configuration — structlog + RotatingFileHandler, compact JSON, no stdout."""

import logging
import logging.handlers
import os

import structlog


def configure_logging(
    log_path: str = "logs/shipping-tracker.log",
    log_level: int = logging.WARNING,
) -> None:
    """Configure structlog with a rotating file handler.

    Produces compact JSON (no whitespace). No StreamHandler is added — the tool
    runs silently on stdout for cron compatibility (LOG-03).

    Args:
        log_path: Path to the log file. Parent directory is created if absent.
        log_level: Root logger level. Default WARNING per D-07.
    """
    os.makedirs(os.path.dirname(log_path) or "logs", exist_ok=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),  # compact JSON, no whitespace
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB per D-06
        backupCount=3,  # keep 3 rotations per D-06
    )
    handler.setFormatter(formatter)

    # WR-03: idempotent — remove and close any existing root handlers before
    # adding ours. Without this, every configure_logging() call (one per main()
    # run, and several across the test suite) would append another
    # RotatingFileHandler, leaking file descriptors and duplicating log lines.
    root_logger = logging.getLogger()
    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)
        existing.close()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    # NO StreamHandler — cron silence (D-07, LOG-03)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
