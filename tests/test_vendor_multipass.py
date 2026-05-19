import json
import subprocess
import sys
from pathlib import Path


def test_vendor_multipass_dry_run_selects_platform_asset(tmp_path):
    manifest = tmp_path / "multipass.lock.json"
    manifest.write_text(
        json.dumps(
            {
                "preferred_version": "1.16.2",
                "min_version": "1.13.0",
                "allow_newer": True,
                "blocked_versions": [],
                "assets": [
                    {
                        "platform": "windows",
                        "arch": "x86_64",
                        "kind": "msi",
                        "version": "1.16.1",
                        "file_name": "multipass.msi",
                        "asset_url": "https://example.invalid/multipass.msi",
                        "sha256": "0" * 64,
                    }
                ],
            }
        )
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "vendor_multipass.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--manifest",
            str(manifest),
            "--platform",
            "windows",
            "--arch",
            "x64",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Selected Multipass 1.16.1" in result.stdout
    assert "multipass.msi" in result.stdout
