from click.testing import CliRunner

from requestor.cli.commands import cli as requestor_cli
from requestor import cli as cli_pkg  # ensure package import works


def test_root_help_lists_groups(monkeypatch):
    # Avoid any side effects from config initialization in callback
    import requestor.cli.commands as commands
    monkeypatch.setattr(commands, "ensure_config", lambda: None)

    runner = CliRunner()
    result = runner.invoke(requestor_cli, ["--help"]) 
    assert result.exit_code == 0
    assert "VM management commands" in result.output
    # Top-level groups
    assert "vm" in result.output
    assert "server" in result.output
    assert "wallet" in result.output


def test_vm_group_help_lists_commands(monkeypatch):
    import requestor.cli.commands as commands
    monkeypatch.setattr(commands, "ensure_config", lambda: None)

    runner = CliRunner()
    result = runner.invoke(requestor_cli, ["vm", "--help"]) 
    assert result.exit_code == 0
    for cmd in [
        "list", "info", "create", "destroy", "delete", "ssh", "connect", "start", "stop", "stats", "providers", "stream"
    ]:
        assert cmd in result.output


def test_vm_stream_group_help_lists_commands(monkeypatch):
    import requestor.cli.commands as commands
    monkeypatch.setattr(commands, "ensure_config", lambda: None)

    runner = CliRunner()
    result = runner.invoke(requestor_cli, ["vm", "stream", "--help"]) 
    assert result.exit_code == 0
    # Newly added 'list' plus existing subcommands
    for cmd in ["list", "status", "inspect", "open", "topup"]:
        assert cmd in result.output


def test_wallet_group_help(monkeypatch):
    import requestor.cli.commands as commands
    monkeypatch.setattr(commands, "ensure_config", lambda: None)

    runner = CliRunner()
    result = runner.invoke(requestor_cli, ["wallet", "--help"]) 
    assert result.exit_code == 0
    assert "faucet" in result.output


def test_server_group_help_and_api_help(monkeypatch):
    import requestor.cli.commands as commands
    monkeypatch.setattr(commands, "ensure_config", lambda: None)

    runner = CliRunner()
    result = runner.invoke(requestor_cli, ["server", "--help"]) 
    assert result.exit_code == 0
    assert "api" in result.output

    # API subcommand help
    result2 = runner.invoke(requestor_cli, ["server", "api", "--help"]) 
    assert result2.exit_code == 0
    for opt in ["--host", "--port", "--reload"]:
        assert opt in result2.output

