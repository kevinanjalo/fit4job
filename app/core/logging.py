"""Application-wide logging configuration with rotating file handler."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def configure_logging() -> None:
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)
        fileh = RotatingFileHandler(LOG_DIR / "fit4job.log", maxBytes=2_000_000, backupCount=5)
        fileh.setFormatter(fmt)
        root.addHandler(fileh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
