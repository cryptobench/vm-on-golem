import importlib.util
import sys
from pathlib import Path


def load_local_stack_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "local_stack.py"
    spec = importlib.util.spec_from_file_location("vm_on_golem_local_stack", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_local_stack_binds_provider_for_guest_metrics():
    local_stack = load_local_stack_module()
    services = local_stack.build_services(
        include_gui=False,
        deployment={
            "rpc_url": "http://127.0.0.1:8545",
            "stream_payment_address": "0x0000000000000000000000000000000000000000",
            "glm_token_address": "0x0000000000000000000000000000000000000000",
        },
    )

    provider = next(service for service in services if service.name == "provider")

    assert provider.env["GOLEM_PROVIDER_HOST"] == "0.0.0.0"
    assert provider.env["GOLEM_PROVIDER_PUBLIC_IP"] == "127.0.0.1"
