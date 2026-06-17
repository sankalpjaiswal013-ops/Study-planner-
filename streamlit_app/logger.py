"""
logger.py

Production-ready logging utilities for StudyPlanner.

Provides:
- `get_logger()` — configured RotatingFileHandler writing to `logs/app.log`
- `mask_secret()` — mask API keys and other sensitive strings

Designed to be simple for beginners and safe for production use.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import json

# Log directory and file
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def mask_secret(value: str, unmasked: int = 4) -> str:
    """Mask a secret string, keeping only the last `unmasked` characters.

    Example: mask_secret("abcd1234") -> "****1234"
    """
    if not value:
        return ""
    try:
        s = str(value)
        if len(s) <= unmasked:
            return "*" * len(s)
        return "*" * (len(s) - unmasked) + s[-unmasked:]
    except Exception:
        return "****"


def get_logger(name: str = "studyplanner") -> logging.Logger:
    """Return a logger configured with RotatingFileHandler.

    - maxBytes: 5MB
    - backupCount: 5
    Logs are written as plain text; structured JSON payloads can be logged
    by passing JSON strings as the message.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fmt = "%(asctime)s %(levelname)s %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

    # Also log to console for developer convenience
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(fmt))
    logger.addHandler(console)

    return logger


# Provide a module-level default logger
logger = get_logger()
