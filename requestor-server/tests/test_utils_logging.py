import logging
from pathlib import Path
import io
import logging

import pytest

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.utils.logging import LogLevel, setup_logger


def test_custom_methods_exist():
    logger = setup_logger("test.custom")
    for method in ("command", "process", "success", "detail"):
        assert hasattr(logger, method)


def test_setup_logger_debug_env(monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    logger = setup_logger("test.debug")
    assert logger.level == logging.DEBUG


def test_setup_logger_default_info(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)
    logger = setup_logger("test.info")
    assert logger.level == logging.INFO


def test_logger_command_logs():
    logger = setup_logger("test.log")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(LogLevel.COMMAND.value)
    logger.addHandler(handler)
    logger.setLevel(LogLevel.COMMAND.value)
    logger.command("hello")
    handler.flush()
    assert "hello" in stream.getvalue()
