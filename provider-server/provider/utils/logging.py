import logging
import colorlog
import sys
import os
from typing import Optional

# Import standard logging levels
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

# Custom log levels
PROCESS = 25  # Between INFO and WARNING
SUCCESS = 35  # Between WARNING and ERROR

# Add custom levels to logging
logging.addLevelName(PROCESS, 'PROCESS')
logging.addLevelName(SUCCESS, 'SUCCESS')

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
        target_level = logging.CRITICAL if silence else (logging.DEBUG if debug else logging.INFO)
        logger.setLevel(target_level)
        for h in logger.handlers:
            try:
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
            'DEBUG': 'cyan',
            'INFO': 'green',
            'PROCESS': 'yellow',
            'WARNING': 'yellow',
            'SUCCESS': 'green,bold',
            'ERROR': 'red',
            'CRITICAL': 'red,bold',
        }
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Apply level based on silence/debug
    logger.setLevel(logging.CRITICAL if silence else (logging.DEBUG if debug else logging.INFO))
    
    return logger

# Create default logger
logger = setup_logger()
