import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def load_build_provider_cli_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_provider_cli.py"
    spec = importlib.util.spec_from_file_location(
        "vm_on_golem_build_provider_cli", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_provider_sidecar_build_collects_pycryptodome(monkeypatch, tmp_path):
    build_provider_cli = load_build_provider_cli_module()
    captured = {}
    cpuid_binary = tmp_path / "site-packages" / "Crypto" / "Util" / "_cpuid_c.abi3.so"

    monkeypatch.setattr(build_provider_cli, "ROOT", tmp_path)
    monkeypatch.setattr(build_provider_cli, "ENTRY", tmp_path / "cli_runner.py")
    monkeypatch.setattr(build_provider_cli, "ensure_pyinstaller", lambda: None)
    monkeypatch.setattr(build_provider_cli.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        build_provider_cli,
        "collect_extension_binaries",
        lambda package: [(cpuid_binary, "Crypto/Util")],
    )

    def fake_run(args, cwd, check):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["check"] = check
        artifact = tmp_path / "dist" / "golem-provider"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("#!/bin/sh\n")

    monkeypatch.setattr(build_provider_cli.subprocess, "run", fake_run)

    artifact = build_provider_cli.build(onefile=True)

    assert artifact == tmp_path / "dist" / "golem-provider"
    assert captured["check"] is True
    assert captured["cwd"] == str(tmp_path)
    assert "--collect-all" in captured["args"]
    crypto_index = captured["args"].index("--collect-all")
    assert captured["args"][crypto_index + 1] == "Crypto"
    assert "--add-binary" in captured["args"]
    binary_index = captured["args"].index("--add-binary")
    assert (
        captured["args"][binary_index + 1]
        == f"{cpuid_binary}{build_provider_cli.os.pathsep}Crypto/Util"
    )


def test_collect_extension_binaries_preserves_package_paths(monkeypatch, tmp_path):
    build_provider_cli = load_build_provider_cli_module()
    package_dir = tmp_path / "site-packages" / "Crypto"
    util_dir = package_dir / "Util"
    util_dir.mkdir(parents=True)
    binary = util_dir / "_cpuid_c.abi3.so"
    ignored = util_dir / "_cpu_features.py"
    binary.write_bytes(b"")
    ignored.write_text("")

    monkeypatch.setattr(
        build_provider_cli.importlib.util,
        "find_spec",
        lambda package: SimpleNamespace(submodule_search_locations=[str(package_dir)]),
    )

    assert build_provider_cli.collect_extension_binaries("Crypto") == [
        (binary, "Crypto/Util")
    ]
