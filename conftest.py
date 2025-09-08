import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "provider-server"))
sys.path.insert(0, str(ROOT / "requestor-server"))

# Provide a dummy multipass binary path for tests
os.environ.setdefault("GOLEM_PROVIDER_MULTIPASS_BINARY_PATH", "/bin/true")
