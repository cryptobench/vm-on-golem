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
    logger.handlers = []  # Clear existing handlers
    
    # Fancy handler for important logs
    fancy_handler = colorlog.StreamHandler(sys.stdout)
    fancy_formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'INFO': 'green',
            'PROCESS': 'yellow',
            'WARNING': 'yellow',
            'SUCCESS': 'green,bold',
            'ERROR': 'red',
            'CRITICAL': 'red,bold',
        },
        secondary_log_colors={},
        style='%'
    )
    fancy_handler.setFormatter(fancy_formatter)
    fancy_handler.addFilter(lambda record: record.levelno in [INFO, PROCESS, SUCCESS, WARNING, ERROR, CRITICAL])
    logger.addHandler(fancy_handler)
    
    if debug:
        # Debug handler for detailed logs
        debug_handler = logging.StreamHandler(sys.stdout)
        debug_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        debug_handler.setFormatter(debug_formatter)
        debug_handler.addFilter(lambda record: record.levelno == DEBUG)
        logger.addHandler(debug_handler)
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    return logger

# Create default logger
logger = setup_logger()
