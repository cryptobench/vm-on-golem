import hashlib
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


def test_posix_installer_latest_selects_release_with_cli_assets(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/bin/sh
set -eu

url=""
for arg in "$@"; do
  case "$arg" in
    http://*|https://*) url="$arg" ;;
  esac
done

case "$url" in
  *api.github.com/repos/example/vm/releases*)
    cat <<'JSON'
[
  {"tag_name":"central-discovery-v0.1.4","assets":[{"name":"checksums.txt"}]},
  {"tag_name":"provider-desktop-v0.1.2","assets":[{"name":"desktop.pkg"}]},
  {"tag_name":"provider-desktop-v0.1.1","assets":[
    {"name":"golem-provider-cli-macos-arm64"},
    {"name":"checksums.txt"}
  ]}
]
JSON
    ;;
  *provider-desktop-v0.1.1/golem-provider-cli-macos-arm64|*provider-desktop-v0.1.1/checksums.txt)
    ;;
  *)
    exit 22
    ;;
esac
""",
    )
    fake_curl.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "GOLEM_PROVIDER_INSTALLER_OS": "Darwin",
        "GOLEM_PROVIDER_INSTALLER_ARCH": "arm64",
        "GOLEM_PROVIDER_INSTALLER_REPO": "example/vm",
    }

    result = subprocess.run(
        [
            "sh",
            str(ROOT / "install" / "provider-cli.sh"),
            "--dry-run",
            "--install-dir",
            "/tmp/golem-provider-bin",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "tag=provider-desktop-v0.1.1" in result.stdout
    assert "asset=golem-provider-cli-macos-arm64" in result.stdout


def test_posix_installer_installs_and_runs_verified_cli_asset(tmp_path):
    release_dir = tmp_path / "release"
    install_dir = tmp_path / "install"
    release_dir.mkdir()
    asset = release_dir / "golem-provider-cli-macos-arm64"
    asset.write_text(
        """#!/bin/sh
set -eu
if [ "$1" = "requirements" ] && [ "$2" = "check" ]; then
  echo "requirements ok"
  exit 0
fi
echo "unexpected command: $*" >&2
exit 2
"""
    )
    asset.chmod(0o755)
    checksum = hashlib.sha256(asset.read_bytes()).hexdigest()
    (release_dir / "checksums.txt").write_text(f"{checksum}  {asset.name}\n")
    env = {
        **os.environ,
        "GOLEM_PROVIDER_INSTALLER_OS": "Darwin",
        "GOLEM_PROVIDER_INSTALLER_ARCH": "arm64",
        "GOLEM_PROVIDER_INSTALLER_BASE_URL": release_dir.as_uri(),
    }

    result = subprocess.run(
        [
            "sh",
            str(ROOT / "install" / "provider-cli.sh"),
            "--version",
            "provider-desktop-v0.1.0",
            "--install-dir",
            str(install_dir),
            "--no-multipass",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    installed = install_dir / "golem-provider"
    assert result.returncode == 0, result.stderr
    assert "requirements ok" in result.stdout
    assert "Golem Provider CLI installed" in result.stdout
    assert installed.exists()
    assert os.access(installed, os.X_OK)


def test_provider_desktop_release_workflow_publishes_cli_assets():
    workflow = (ROOT / ".github" / "workflows" / "release-provider-desktop.yml").read_text()

    assert "--release-dir ../provider-cli-release-assets" in workflow
    assert "Upload provider CLI artifact" in workflow
    assert "pattern: provider-*" in workflow
    assert "golem-provider-cli-linux-x86_64" in workflow
    assert "golem-provider-cli-macos-arm64" in workflow
    assert "golem-provider-cli-windows-x86_64.exe" in workflow
    assert "Generate release checksums" in workflow
    assert "checksums=\"release-artifacts/checksums.txt\"" in workflow
    assert "awk -v name=\"$(basename \"$file\")\" '{print $1 \"  \" name}'" in workflow
    assert 'FILENAME="$(basename "$file")"' not in workflow


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
