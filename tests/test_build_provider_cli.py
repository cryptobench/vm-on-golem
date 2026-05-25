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


def test_provider_cli_release_asset_names():
    build_provider_cli = load_build_provider_cli_module()

    assert (
        build_provider_cli.release_asset_name("linux-x86_64")
        == "golem-provider-cli-linux-x86_64"
    )
    assert (
        build_provider_cli.release_asset_name("macos-arm64")
        == "golem-provider-cli-macos-arm64"
    )
    assert (
        build_provider_cli.release_asset_name("windows-x86_64")
        == "golem-provider-cli-windows-x86_64.exe"
    )


def test_provider_cli_stage_release_asset(tmp_path):
    build_provider_cli = load_build_provider_cli_module()
    exe = tmp_path / "dist" / "golem-provider"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n")

    out = build_provider_cli.stage_release_asset(
        exe, tmp_path / "release", "linux-x86_64"
    )

    assert out == tmp_path / "release" / "golem-provider-cli-linux-x86_64"
    assert out.read_text() == "#!/bin/sh\n"


def test_provider_cli_stage_accepts_target_triple_override(monkeypatch, tmp_path):
    build_provider_cli = load_build_provider_cli_module()
    exe = tmp_path / "dist" / "golem-provider"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n")

    monkeypatch.setattr(build_provider_cli, "TAURI_BINARIES", tmp_path / "binaries")
    monkeypatch.setattr(
        build_provider_cli,
        "detect_target_triple",
        lambda: (_ for _ in ()).throw(AssertionError("should not detect target")),
    )

    out = build_provider_cli.stage(exe, "x86_64-unknown-linux-gnu")

    assert out == tmp_path / "binaries" / "golem-provider-x86_64-unknown-linux-gnu"
    assert out.read_text() == "#!/bin/sh\n"
