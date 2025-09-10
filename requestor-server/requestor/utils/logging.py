import logging
import colorlog
import sys
import os
from typing import Optional
from enum import Enum

# Import standard logging levels
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

class LogLevel(Enum):
    """Custom log levels for enhanced CLI experience."""
    COMMAND = 15  # For CLI commands
    PROCESS = 25  # For ongoing processes
    SUCCESS = 35  # For successful operations
    DETAIL = 22   # For additional details

# Add custom levels to logging
logging.addLevelName(LogLevel.COMMAND.value, 'COMMAND')
logging.addLevelName(LogLevel.PROCESS.value, 'PROCESS')
logging.addLevelName(LogLevel.SUCCESS.value, 'SUCCESS')
logging.addLevelName(LogLevel.DETAIL.value, 'DETAIL')

def command(self, message, *args, **kwargs):
    """Log CLI command with a distinctive style."""
    if self.isEnabledFor(LogLevel.COMMAND.value):
        self._log(LogLevel.COMMAND.value, message, args, **kwargs)

def process(self, message, *args, **kwargs):
    """Log ongoing process with a progress indicator."""
    if self.isEnabledFor(LogLevel.PROCESS.value):
        self._log(LogLevel.PROCESS.value, f"⚡ {message}", args, **kwargs)

def success(self, message, *args, **kwargs):
    """Log successful operation with a checkmark."""
    if self.isEnabledFor(LogLevel.SUCCESS.value):
        self._log(LogLevel.SUCCESS.value, f"✨ {message}", args, **kwargs)

def detail(self, message, *args, **kwargs):
    """Log additional details with an arrow."""
    if self.isEnabledFor(LogLevel.DETAIL.value):
        self._log(LogLevel.DETAIL.value, f"  → {message}", args, **kwargs)

# Add methods to Logger class
logging.Logger.command = command
logging.Logger.process = process
logging.Logger.success = success
logging.Logger.detail = detail

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """Setup and return a colored logger optimized for CLI experience.
    
    Args:
        name: Logger name (optional)
        
    Returns:
        Configured logger instance with fancy formatting
    """
    logger = logging.getLogger(name or __name__)
    logger.handlers = []  # Clear existing handlers
    
    # Check DEBUG environment variable
    debug = os.getenv('DEBUG', '').lower() in ('1', 'true', 'yes')
    # Global silence switch for JSON/machine outputs
    silence = os.getenv('GOLEM_SILENCE_LOGS', '').lower() in ('1', 'true', 'yes')
    
    # Prevent duplicate logs by removing root handlers
    root = logging.getLogger()
    root.handlers = []
    
    # Fancy handler for CLI output
    fancy_handler = colorlog.StreamHandler(sys.stderr)  # Use stderr for logs
    fancy_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(message)s%(reset)s",
        reset=True,
        log_colors={
            'DEBUG': 'blue',
            'INFO': 'white',
            'COMMAND': 'bold_cyan',
            'DETAIL': 'cyan',
            'PROCESS': 'yellow',
            'WARNING': 'yellow',
            'SUCCESS': 'bold_green',
            'ERROR': 'bold_red',
            'CRITICAL': 'bold_red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )
    fancy_handler.setFormatter(fancy_formatter)
    # Suppress DEBUG unless DEBUG=1; suppress everything if silence
    def _filter(record: logging.LogRecord) -> bool:
        if silence:
            return False
        return (record.levelno != DEBUG) or debug
    fancy_handler.addFilter(_filter)
    logger.addHandler(fancy_handler)
    logger.propagate = False  # Prevent propagation to avoid duplicates
    
    if silence:
        logger.setLevel(CRITICAL)
        # Silence common libraries and root logger
        logging.getLogger().setLevel(CRITICAL)
        logging.getLogger('asyncio').setLevel(CRITICAL)
        logging.getLogger('aiosqlite').setLevel(CRITICAL)
    elif debug:
        logger.setLevel(DEBUG)
        # Enable debug logging for other libraries
        logging.getLogger('asyncio').setLevel(DEBUG)
        logging.getLogger('aiosqlite').setLevel(DEBUG)
    else:
        logger.setLevel(INFO)
        # Suppress debug logs from other libraries
        logging.getLogger('asyncio').setLevel(WARNING)
        logging.getLogger('aiosqlite').setLevel(WARNING)
    
    return logger

# Create default logger
logger = setup_logger('golem.requestor')
