"""
Entry point script to bundle the Provider CLI with PyInstaller.

Build example:
  pyinstaller -F -n golem-provider provider-server/cli_runner.py
"""

from provider.main import cli


if __name__ == "__main__":
    cli()

