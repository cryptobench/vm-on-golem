import logging
import os
import sys

# Import standard logging levels
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import colorlog

# Custom log levels
PROCESS = 25  # Between INFO and WARNING
SUCCESS = 35  # Between WARNING and ERROR
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUPS = 5

# Add custom levels to logging
logging.addLevelName(PROCESS, "PROCESS")
logging.addLevelName(SUCCESS, "SUCCESS")


def process(self, message, *args, **kwargs):
    """Log 'msg % args' with severity 'PROCESS'."""
    if self.isEnabledFor(PROCESS):
        self._log(PROCESS, message, args, **kwargs)


def success(self, message, *args, **kwargs):
    """Log 'msg % args' with severity 'SUCCESS'."""
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


# Add methods to Logger class
logging.Logger.process = process
logging.Logger.success = success


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _provider_log_path() -> Path | None:
    raw_dir = os.getenv("GOLEM_PROVIDER_LOG_DIR")
    if not raw_dir:
        return None
    log_dir = Path(raw_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "provider.log"


def _ensure_file_handler(logger: logging.Logger, debug: bool) -> None:
    log_path = _provider_log_path()
    if log_path is None:
        return
    for handler in logger.handlers:
        if getattr(handler, "_golem_provider_file_handler", False):
            return
    handler = RotatingFileHandler(
        log_path,
        maxBytes=_env_int("GOLEM_PROVIDER_LOG_MAX_BYTES", DEFAULT_LOG_MAX_BYTES),
        backupCount=_env_int("GOLEM_PROVIDER_LOG_BACKUPS", DEFAULT_LOG_BACKUPS),
        encoding="utf-8",
    )
    handler._golem_provider_file_handler = True  # type: ignore[attr-defined]
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)


def setup_logger(name: Optional[str] = None, debug: bool = False) -> logging.Logger:
    """Setup and return a colored logger.

    Args:
        name: Logger name (optional)
        debug: Whether to show debug logs (optional)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or __name__)

    # Global hard mute for JSON commands or other machine output scenarios
    silence = os.getenv("GOLEM_SILENCE_LOGS", "").lower() in ("1", "true", "yes")

    # If already configured, still adjust level according to silence/debug
    if logger.handlers:
        target_level = (
            logging.CRITICAL if silence else (logging.DEBUG if debug else logging.INFO)
        )
        logger.setLevel(target_level)
        _ensure_file_handler(logger, debug)
        for h in logger.handlers:
            try:
                if getattr(h, "_golem_provider_file_handler", False):
                    h.setLevel(logging.DEBUG if debug else logging.INFO)
                else:
                    h.setLevel(target_level)
            except Exception:
                pass
        return logger  # Already configured (levels updated)

    # Send logs to stderr so stdout can be reserved for machine output (e.g., --json)
    handler = colorlog.StreamHandler(sys.stderr)
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "PROCESS": "yellow",
            "WARNING": "yellow",
            "SUCCESS": "green,bold",
            "ERROR": "red",
            "CRITICAL": "red,bold",
        },
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    _ensure_file_handler(logger, debug)
    # Apply level based on silence/debug
    logger.setLevel(
        logging.CRITICAL if silence else (logging.DEBUG if debug else logging.INFO)
    )

    return logger


# Create default logger
logger = setup_logger()
