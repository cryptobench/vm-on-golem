import os

# Ensure provider config bootstrap is skipped in tests to avoid filesystem writes
os.environ.setdefault("GOLEM_PROVIDER_SKIP_BOOTSTRAP", "1")

# Provide a dummy private key to avoid EthereumIdentity file I/O
os.environ.setdefault(
    "GOLEM_PROVIDER_ETHEREUM_PRIVATE_KEY",
    "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)

# Avoid auto-detecting multipass binary during settings load
os.environ.setdefault("GOLEM_PROVIDER_MULTIPASS_BINARY_PATH", "/bin/echo")

# Provide a PUBLIC_IP to avoid any detection logic in advertisers/tests
os.environ.setdefault("GOLEM_PROVIDER_PUBLIC_IP", "127.0.0.1")

# Make retries/timeouts fast in tests to avoid long waits
os.environ.setdefault("GOLEM_PROVIDER_RETRY_ATTEMPTS", "1")
os.environ.setdefault("GOLEM_PROVIDER_RETRY_DELAY_SECONDS", "0.05")
os.environ.setdefault("GOLEM_PROVIDER_RETRY_BACKOFF", "1.0")
os.environ.setdefault("GOLEM_PROVIDER_CREATE_VM_MAX_RETRIES", "2")
os.environ.setdefault("GOLEM_PROVIDER_CREATE_VM_RETRY_DELAY_SECONDS", "0.05")
os.environ.setdefault("GOLEM_PROVIDER_LAUNCH_TIMEOUT_SECONDS", "5")
