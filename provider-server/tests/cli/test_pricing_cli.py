from typer.testing import CliRunner
import tempfile
import os
import re

from provider.main import cli


def test_cli_pricing_set_and_show(monkeypatch):
    runner = CliRunner()

    # Redirect env path to temp file
    tmpdir = tempfile.TemporaryDirectory()
    env_path = os.path.join(tmpdir.name, ".env.test")

    from provider import main as main_mod

    monkeypatch.setattr(main_mod, "_env_path_for", lambda dev: env_path)

    # Fix GLM price
    from provider.utils import pricing as pricing_mod
    monkeypatch.setattr(pricing_mod, "fetch_glm_usd_price", lambda: None)

    # Set
    result = runner.invoke(
        cli,
        [
            "pricing",
            "set",
            "--core-usd",
            "6",
            "--ram-usd",
            "2.5",
            "--storage-usd",
            "0.12",
        ],
    )
    assert result.exit_code == 0
    assert os.path.exists(env_path)
    content = open(env_path).read()
    assert "GOLEM_PROVIDER_PRICE_USD_PER_CORE_MONTH=6" in content
    assert "GOLEM_PROVIDER_PRICE_USD_PER_GB_RAM_MONTH=2.5" in content
    assert "GOLEM_PROVIDER_PRICE_USD_PER_GB_STORAGE_MONTH=0.12" in content

    # Show (with mocked price available)
    monkeypatch.setattr(pricing_mod, "fetch_glm_usd_price", lambda: 0.5)
    result2 = runner.invoke(cli, ["pricing", "show"])
    assert result2.exit_code == 0
    # Includes example header and some GLM text
    assert "Example monthly costs with current settings:" in result2.stdout


def test_cli_pricing_set_negative(monkeypatch):
    runner = CliRunner()
    from provider import main as main_mod
    monkeypatch.setattr(main_mod, "_env_path_for", lambda dev: os.devnull)
    result = runner.invoke(
        cli,
        [
            "pricing",
            "set",
            "--core-usd",
            "-1",
            "--ram-usd",
            "0",
            "--storage-usd",
            "0",
        ],
    )
    assert result.exit_code != 0


def test_cli_pricing_show_requires_price(monkeypatch):
    runner = CliRunner()
    from provider.utils import pricing as pricing_mod
    # Simulate failure to fetch price
    monkeypatch.setattr(pricing_mod, "fetch_glm_usd_price", lambda: None)
    result = runner.invoke(cli, ["pricing", "show"])
    assert result.exit_code != 0
    assert "Could not fetch GLM/USD price" in result.stdout


def test_cli_pricing_show_with_price(monkeypatch):
    runner = CliRunner()
    from provider.utils import pricing as pricing_mod
    # Provide a fixed price and verify USD appears in examples
    monkeypatch.setattr(pricing_mod, "fetch_glm_usd_price", lambda: 0.5)
    result = runner.invoke(cli, ["pricing", "show"])
    assert result.exit_code == 0
    assert "Example monthly costs with current settings:" in result.stdout
    assert "USD/GLM" in result.stdout
