import sys
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "provider-server"))
sys.path.insert(0, str(ROOT / "requestor-server"))

# Provide safe environment for provider settings during test collection
os.environ.setdefault("GOLEM_PROVIDER_SKIP_BOOTSTRAP", "1")
os.environ.setdefault(
    "GOLEM_PROVIDER_ETHEREUM_PRIVATE_KEY",
    "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)

_tmp = tempfile.mkdtemp(prefix="golem-test-")
os.environ.setdefault("GOLEM_PROVIDER_SSH_KEY_DIR", os.path.join(_tmp, "ssh"))
os.environ.setdefault("GOLEM_PROVIDER_VM_DATA_DIR", os.path.join(_tmp, "vms"))
os.environ.setdefault("GOLEM_PROVIDER_CLOUD_INIT_DIR", os.path.join(_tmp, "cloud-init"))
os.environ.setdefault("GOLEM_PROVIDER_PROXY_STATE_DIR", os.path.join(_tmp, "proxy"))

# Multipass binary path to a known executable (python itself)
os.environ.setdefault("GOLEM_PROVIDER_MULTIPASS_BINARY_PATH", sys.executable)
os.environ.setdefault("GOLEM_PROVIDER_PUBLIC_IP", "127.0.0.1")
