import asyncio
from pathlib import Path

import pytest

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.utils.spinner import Spinner, step


def test_spinner_success_output(capsys):
    with Spinner("work"):
        pass
    out = capsys.readouterr().out
    assert "✓ work" in out


def test_spinner_failure_output(capsys):
    with pytest.raises(ValueError):
        with Spinner("fail"):
            raise ValueError("boom")
    out = capsys.readouterr().out
    assert "✗ fail" in out


@pytest.mark.asyncio
async def test_step_decorator_returns_value():
    @step("doing")
    async def sample():
        await asyncio.sleep(0)
        return 5

    assert await sample() == 5
