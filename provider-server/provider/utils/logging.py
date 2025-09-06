import logging
import colorlog
import sys
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
    if logger.handlers:
        return logger  # Already configured

    handler = colorlog.StreamHandler(sys.stdout)
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
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    return logger

# Create default logger
logger = setup_logger()
