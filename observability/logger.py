"""Structured logging with JSON support and context fields."""
import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any

import config


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "structured"):
            data: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            extra = getattr(record, "structured", {})
            if extra:
                data.update(extra)
            return json.dumps(data)
        return super().format(record)


def setup_logging(structured: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    if not root.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        if structured:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            ))

        config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

        root.addHandler(console_handler)
        root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_structured(logger: logging.Logger, level: int, message: str, **kwargs) -> None:
    record = logger.makeRecord(logger.name, level, "", 0, message, (), None)
    record.structured = kwargs
    logger.handle(record)
