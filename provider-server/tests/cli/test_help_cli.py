from typer.testing import CliRunner

from provider.main import cli


def test_cli_root_help_lists_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Core command groups
    assert "start" in result.stdout
    assert "doctor" in result.stdout
    assert "vm" in result.stdout
    assert "stream" in result.stdout
    assert "monitor" in result.stdout
    assert "alert" in result.stdout
    assert "webhook" in result.stdout
    assert "settings" in result.stdout
    assert "pricing" in result.stdout
    assert "streams" in result.stdout
    assert "restart" not in result.stdout
    assert "logs" not in result.stdout
    assert "stop" not in result.stdout
    assert " up " not in result.stdout
    assert " down " not in result.stdout


def test_cli_group_help_pricing():
    runner = CliRunner()
    result = runner.invoke(cli, ["pricing", "--help"])
    assert result.exit_code == 0
    assert "show" in result.stdout
    assert "set" in result.stdout


def test_cli_group_help_streams():
    runner = CliRunner()
    result = runner.invoke(cli, ["streams", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "show" in result.stdout
    assert "earnings" in result.stdout
    assert "withdraw" in result.stdout


def test_cli_start_help_options_present():
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--help"])
    assert result.exit_code == 0
    assert "--no-verify-port" in result.stdout
    assert "--network" in result.stdout
    assert "--foreground" not in result.stdout
    assert "--background" not in result.stdout
    assert "--daemon" not in result.stdout
    assert "--timeout" not in result.stdout
    assert "--gui" not in result.stdout


def test_headless_group_help_lists_simple_commands():
    runner = CliRunner()

    vm = runner.invoke(cli, ["vm", "--help"])
    assert vm.exit_code == 0
    assert "list" in vm.stdout
    assert "show" in vm.stdout
    assert "access" in vm.stdout
    assert "terminate" in vm.stdout

    stream = runner.invoke(cli, ["stream", "--help"])
    assert stream.exit_code == 0
    assert "list" in stream.stdout
    assert "show" in stream.stdout
    assert "earnings" in stream.stdout
    assert "withdraw" in stream.stdout

    settings = runner.invoke(cli, ["settings", "--help"])
    assert settings.exit_code == 0
    assert "resources" in settings.stdout
    assert "pricing" in settings.stdout
