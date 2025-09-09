from typer.testing import CliRunner

from provider.main import cli


def test_cli_root_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Core command groups
    assert "start" in result.stdout
    assert "pricing" in result.stdout
    assert "wallet" in result.stdout
    assert "streams" in result.stdout


def test_cli_group_help_pricing():
    runner = CliRunner()
    result = runner.invoke(cli, ["pricing", "--help"])
    assert result.exit_code == 0
    assert "show" in result.stdout
    assert "set" in result.stdout


def test_cli_group_help_wallet():
    runner = CliRunner()
    result = runner.invoke(cli, ["wallet", "--help"])
    assert result.exit_code == 0
    assert "faucet-l2" in result.stdout


def test_cli_group_help_streams():
    runner = CliRunner()
    result = runner.invoke(cli, ["streams", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "show" in result.stdout


def test_cli_start_help_options_present():
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--help"])
    assert result.exit_code == 0
    assert "--no-verify-port" in result.stdout
    assert "--network" in result.stdout

