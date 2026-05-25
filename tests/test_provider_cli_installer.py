import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_installer_dry_run(os_name: str, arch: str) -> str:
    env = {
        **os.environ,
        "GOLEM_PROVIDER_INSTALLER_OS": os_name,
        "GOLEM_PROVIDER_INSTALLER_ARCH": arch,
    }
    result = subprocess.run(
        [
            "sh",
            str(ROOT / "install" / "provider-cli.sh"),
            "--dry-run",
            "--version",
            "provider-desktop-v0.1.0",
            "--install-dir",
            "/tmp/golem-provider-bin",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_posix_installer_selects_linux_x86_64_release_asset():
    output = run_installer_dry_run("Linux", "x86_64")

    assert "target=linux-x86_64" in output
    assert "asset=golem-provider-cli-linux-x86_64" in output
    assert (
        "asset_url=https://github.com/cryptobench/vm-on-golem/releases/download/"
        "provider-desktop-v0.1.0/golem-provider-cli-linux-x86_64"
    ) in output
    assert "checksums_url=" in output


def test_posix_installer_allows_release_base_override():
    env = {
        **os.environ,
        "GOLEM_PROVIDER_INSTALLER_OS": "Linux",
        "GOLEM_PROVIDER_INSTALLER_ARCH": "x86_64",
        "GOLEM_PROVIDER_INSTALLER_BASE_URL": "file:///tmp/provider-release",
    }
    result = subprocess.run(
        [
            "sh",
            str(ROOT / "install" / "provider-cli.sh"),
            "--dry-run",
            "--version",
            "provider-desktop-v0.1.0",
            "--install-dir",
            "/tmp/golem-provider-bin",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert (
        "asset_url=file:///tmp/provider-release/golem-provider-cli-linux-x86_64"
        in result.stdout
    )
    assert "checksums_url=file:///tmp/provider-release/checksums.txt" in result.stdout


def test_posix_installer_selects_macos_arm64_release_asset():
    output = run_installer_dry_run("Darwin", "arm64")

    assert "target=macos-arm64" in output
    assert "asset=golem-provider-cli-macos-arm64" in output


def test_posix_installer_rejects_unsupported_target():
    env = {
        **os.environ,
        "GOLEM_PROVIDER_INSTALLER_OS": "Linux",
        "GOLEM_PROVIDER_INSTALLER_ARCH": "aarch64",
    }
    result = subprocess.run(
        [
            "sh",
            str(ROOT / "install" / "provider-cli.sh"),
            "--dry-run",
            "--version",
            "provider-desktop-v0.1.0",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "No provider CLI binary is published for linux-arm64 yet" in result.stderr


def test_installers_keep_start_as_only_fast_path_command():
    sh_script = (ROOT / "install" / "provider-cli.sh").read_text()
    ps_script = (ROOT / "install" / "provider-cli.ps1").read_text()

    assert "golem-provider start" in sh_script
    assert "golem-provider start" in ps_script
    assert 'exec "$install_path" start' in sh_script
    assert "& $installPath start" in ps_script
    assert "golem-provider up" not in sh_script
    assert "golem-provider up" not in ps_script
    assert "service install" not in sh_script
    assert "service install" not in ps_script
