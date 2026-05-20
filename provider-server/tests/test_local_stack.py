import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCAL_STACK_PATH = ROOT / "scripts" / "local_stack.py"


def load_local_stack_module():
    spec = importlib.util.spec_from_file_location("local_stack", LOCAL_STACK_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_local_stack_does_not_export_provider_location_overrides(monkeypatch, tmp_path):
    local_stack = load_local_stack_module()
    monkeypatch.setattr(local_stack, "LOCAL_DIR", tmp_path / ".local")
    monkeypatch.setenv("GOLEM_PROVIDER_PUBLIC_IP", "198.51.100.10")
    monkeypatch.setenv("GOLEM_PROVIDER_COUNTRY", "DK")
    monkeypatch.setenv("GOLEM_PROVIDER_PUBLIC_ENDPOINT_IP", "198.51.100.10")
    deployment = {
        "stream_payment_address": "0x1111111111111111111111111111111111111111",
        "glm_token_address": "0x2222222222222222222222222222222222222222",
        "rpc_url": "http://127.0.0.1:8545",
        "ws_url": "ws://127.0.0.1:8545",
    }

    services = local_stack.build_services(
        deployment,
        start_provider_desktop=True,
    )

    forbidden = {
        "GOLEM_PROVIDER_COUNTRY",
        "GOLEM_PROVIDER_PUBLIC_IP",
        "GOLEM_PROVIDER_PUBLIC_ENDPOINT_IP",
    }
    exported = {key for service in services for key in service.env if key in forbidden}
    assert exported == set()
    for service in services:
        merged_env = local_stack.merged_env(service.env, unset=service.unset_env)
        if service.name in {"provider", "provider-desktop"}:
            assert forbidden.isdisjoint(merged_env)
