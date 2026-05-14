# Logging configuration — dual output: colored console + rotating file.

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str = "asentinel", level: str = "INFO") -> logging.Logger:
    """
    Configure and return a logger with console + rotating file handlers.

    Log file is written to webhook/logs/webhook.log (5 MB, 3 backups).
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called more than once
    if logger.handlers:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    fmt = "[%(asctime)s] [%(levelname)-8s] %(name)s — %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler — writes inside the webhook/logs/ directory
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        filename=str(log_dir / "webhook.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logger initialized — level=%s", level)
    return logger


# Module-level singleton
log_level = os.getenv("LOG_LEVEL", "INFO")
logger = setup_logger("asentinel", log_level)
