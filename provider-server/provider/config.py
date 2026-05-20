import json
import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from .utils.logging import setup_logger

logger = setup_logger(__name__)


def normalize_acme_env(value: str | None) -> str:
    """Normalize ACME environment names used for certificate issuance."""
    raw = (value or "production").strip().lower()
    if raw == "staging":
        return "staging"
    if raw in {"production", "prod"}:
        return "production"
    raise ValueError("ACME environment must be 'staging', 'production', or 'prod'")


def derive_port_check_url(discovery_ws_url: str) -> str:
    """Derive the shared port-check HTTP origin from a central discovery WS URL."""
    parsed = urlsplit(discovery_ws_url)
    if parsed.scheme == "ws":
        scheme = "http"
    elif parsed.scheme == "wss":
        scheme = "https"
    else:
        raise ValueError("Discovery websocket URL must use ws:// or wss://")
    if not parsed.netloc:
        raise ValueError("Discovery websocket URL must include a host")
    return urlunsplit((scheme, parsed.netloc, "", "", ""))


def ensure_config() -> None:
    """Ensure the provider configuration directory and defaults exist."""
    base_dir = Path.home() / ".golem" / "provider"
    env_file = base_dir / ".env"
    subdirs = ["keys", "ssh", "vms", "proxy"]
    created = False

    for sub in subdirs:
        path = base_dir / sub
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created = True

    if not env_file.exists():
        env_file.write_text("GOLEM_ENVIRONMENT=production\n")
        created = True

    from .security.ethereum import EthereumIdentity

    identity = EthereumIdentity(str(base_dir / "keys"))
    if not identity.key_file.exists():
        identity.get_or_create_identity()
        created = True

    if created:
        # Inform the user, but write to stderr so JSON outputs on stdout remain clean
        logger.info("Using default settings – run with --help to customize")


if not os.environ.get("GOLEM_PROVIDER_SKIP_BOOTSTRAP") and not os.environ.get(
    "PYTEST_CURRENT_TEST"
):
    ensure_config()


class Settings(BaseSettings):
    """Provider configuration settings."""

    # API Settings
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 7466
    SKIP_PORT_VERIFICATION: bool = False
    REQUESTOR_SESSION_SECRET: str = Field(
        default="",
        description="Optional signing secret for provider-issued requestor VM sessions.",
    )
    REQUESTOR_SESSION_TTL_SECONDS: int = Field(
        default=86400,
        description="Maximum lifetime for provider-issued requestor API sessions.",
    )
    PROVIDER_ADMIN_TOKEN: str = Field(
        default="",
        description="Optional bearer token for provider-owner/admin API access.",
    )
    ENVIRONMENT: str = "production"
    # Logical network selector for advertisement scope and client defaults
    # If not explicitly provided, computed by validator below (dev -> testnet, else -> mainnet)
    NETWORK: str = Field(
        default="", description="Logical Golem network: 'testnet' or 'mainnet'"
    )

    # Payments chain selection (modular network profiles).
    PAYMENTS_NETWORK: str = Field(
        default="hoodi",
        description="Payments network profile (e.g., 'hoodi', 'sepolia', 'mainnet')",
    )

    @field_validator("PAYMENTS_NETWORK", mode="before")
    @classmethod
    def prefer_payments_network_env(cls, v: str) -> str:
        return os.environ.get("GOLEM_PROVIDER_PAYMENTS_NETWORK", v)

    @property
    def DEV_MODE(self) -> bool:
        return self.ENVIRONMENT == "development"

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def prefer_global_env(cls, v: str) -> str:
        """Prefer unified GOLEM_ENVIRONMENT when provided; fallback to service-specific env."""
        ge = os.environ.get("GOLEM_ENVIRONMENT")
        if ge:
            return ge
        return v

    @field_validator("NETWORK", mode="before")
    @classmethod
    def resolve_network(cls, v: str, values: dict) -> str:
        """Resolve logical network with sensible defaults.

        Priority:
        1) Explicit override via GOLEM_PROVIDER_NETWORK env or provided value
        2) If ENVIRONMENT == development -> 'development'
        3) Otherwise -> 'mainnet'
        """
        # Prefer explicit provider-scoped env override
        env_override = os.environ.get("GOLEM_PROVIDER_NETWORK")
        if env_override:
            return env_override
        # If value provided (via settings or direct assignment), keep it
        val = (v or "").strip()
        if val:
            return val
        # Default based on environment
        env = (values.data.get("ENVIRONMENT") or "").lower()
        return "development" if env == "development" else "mainnet"

    @field_validator("SKIP_PORT_VERIFICATION", mode="before")
    def set_skip_verification(cls, v: bool, values: dict) -> bool:
        """Set skip verification based on debug mode."""
        return v or values.data.get("DEBUG", False)

    # Provider Settings
    PROVIDER_NAME: str = "golem-provider"
    PROVIDER_COUNTRY: Optional[str] = None
    ETHEREUM_KEY_DIR: str = ""
    ETHEREUM_PRIVATE_KEY: Optional[str] = None
    PROVIDER_ID: str = ""  # Will be set from Ethereum identity

    @field_validator("ETHEREUM_KEY_DIR", mode="before")
    def resolve_key_dir(cls, v: str) -> str:
        """Resolve Ethereum key directory path."""
        if not v:
            return str(Path.home() / ".golem" / "provider" / "keys")
        path = Path(v)
        if not path.is_absolute():
            path = Path.home() / path
        return str(path)

    @field_validator("ETHEREUM_PRIVATE_KEY", mode="before")
    def get_private_key(cls, v: Optional[str], values: dict) -> str:
        """Get private key from key file if not provided."""
        from provider.security.ethereum import EthereumIdentity

        if v:
            return v

        key_dir = values.data.get("ETHEREUM_KEY_DIR")
        identity = EthereumIdentity(key_dir)
        _, private_key = identity.get_or_create_identity()
        return private_key

    @field_validator("PROVIDER_ID", mode="before")
    def get_provider_id(cls, v: str, values: dict) -> str:
        """Get provider ID from private key."""
        from eth_account import Account

        private_key = values.data.get("ETHEREUM_PRIVATE_KEY")
        if not private_key:
            raise ValueError("ETHEREUM_PRIVATE_KEY is not set")

        acct = Account.from_key(private_key)
        provider_id_from_key = acct.address

        # If ID was provided via env, warn if it doesn't match
        if v and v != provider_id_from_key:
            logger.warning(
                f"Provider ID from env ('{v}') does not match ID from key file ('{provider_id_from_key}'). "
                "Using ID from key file."
            )

        return provider_id_from_key

    @field_validator("PROVIDER_NAME", mode="before")
    def set_provider_name(cls, v: str, values: dict) -> str:
        """Prefix provider name with DEVMODE if in development."""
        if values.data.get("ENVIRONMENT") == "development":
            return f"DEVMODE-{v}"
        return v

    # Discovery settings. Central discovery is websocket-only.
    DISCOVERY_WS_URL: str = Field(
        default="wss://78.46.172.104/api/v1/discovery/providers",
        description="Central discovery provider websocket URL",
    )

    # EVM / Payments
    PAYMENTS_RPC_URL: str = Field(
        default="",
        description="EVM RPC URL for streaming payments; defaults from PAYMENTS_NETWORK profile",
    )
    PAYMENTS_WS_URL: str = Field(
        default="",
        description="EVM WebSocket RPC URL for StreamPayment live events",
    )
    STREAM_PAYMENT_ADDRESS: str = Field(
        default="",
        description="Deployed StreamPayment contract address",
    )
    GLM_TOKEN_ADDRESS: str = Field(
        default="",
        description="GLM ERC20 token address used by StreamPayment.",
    )
    STREAM_MIN_REMAINING_SECONDS: int = Field(
        default=0,
        description="Legacy compatibility setting; streamState drives expiry",
    )
    STREAM_MONITOR_ENABLED: bool = Field(
        default=True,
        description="Enable background monitor to delete VMs after stream expiry",
    )
    STREAM_WITHDRAW_ENABLED: bool = Field(
        default=False, description="Enable background withdrawals for active streams"
    )
    STREAM_MONITOR_INTERVAL_SECONDS: int = Field(
        default=30, description="How frequently to check stream runway"
    )
    STREAM_WITHDRAW_INTERVAL_SECONDS: int = Field(
        default=1800, description="How frequently to attempt withdrawals"
    )
    STREAM_MIN_WITHDRAW_WEI: int = Field(
        default=0,
        description="Min withdrawable amount (wei) before triggering withdraw",
    )

    # Behavior on exhausted runway
    STREAM_REMOVE_MAPPING_ON_EXHAUSTED: bool = Field(
        default=True,
        description="When true, remove the VM->stream mapping after a successful stop on exhausted runway to prevent repeated stop attempts.",
    )
    STREAM_DELETE_ON_EXHAUSTED: bool = Field(
        default=False,
        description="When true, delete the VM entirely once runway is exhausted and the VM has been stopped.",
    )

    # Shutdown behavior
    STOP_VMS_ON_EXIT: bool = Field(
        default=False,
        description="When true, stop all running VMs on provider shutdown. Default keeps VMs running.",
    )

    @field_validator("PAYMENTS_RPC_URL", mode="before")
    @classmethod
    def prefer_custom_env(cls, v: str, values: dict) -> str:
        if v:
            return v
        pn = values.data.get("PAYMENTS_NETWORK") or "hoodi"
        return Settings._profile_defaults(pn)["rpc_url"]

    @field_validator("PAYMENTS_WS_URL", mode="before")
    @classmethod
    def default_payments_ws_url(cls, v: str, values: dict) -> str:
        if v:
            return v
        pn = values.data.get("PAYMENTS_NETWORK") or "hoodi"
        return str(Settings._profile_defaults(pn).get("ws_url", ""))

    @staticmethod
    def _load_deployment(network: str) -> tuple[str | None, str | None]:
        """Try to load default StreamPayment deployment metadata.

        Returns (stream_payment_address, payment_token_address) or (None, None) if not found.
        """
        try:
            # Allow override via env
            base = os.environ.get("GOLEM_DEPLOYMENTS_DIR")
            if base:
                path = Path(base) / f"{Settings._deployment_basename(network)}.json"
            else:
                # repo root = ../../ from this file
                path = (
                    Path(__file__).resolve().parents[2]
                    / "contracts"
                    / "deployments"
                    / f"{Settings._deployment_basename(network)}.json"
                )
            if not path.exists():
                # Try package resource fallback
                try:
                    import importlib.resources as ir

                    with ir.files("provider.data.deployments").joinpath(f"{Settings._deployment_basename(network)}.json").open("r") as fh:  # type: ignore[attr-defined]
                        data = json.load(fh)
                except Exception:
                    return None, None
            else:
                data = json.loads(path.read_text())
            sp = data.get("StreamPayment", {})
            addr = sp.get("address")
            token = sp.get("paymentToken") or sp.get("glmToken")
            if isinstance(addr, str) and addr:
                return addr, token or "0x0000000000000000000000000000000000000000"
        except Exception:
            pass
        return None, None

    @staticmethod
    def _deployment_basename(network: str) -> str:
        n = (network or "").lower()
        if "." in n:
            return n.split(".")[0]
        return n or "hoodi"

    @staticmethod
    def _profile_defaults(network: str) -> dict[str, str | bool]:
        n = (network or "hoodi").lower()
        profiles = {
            "sepolia": {
                "rpc_url": "https://rpc.sepolia.org",
                "ws_url": "",
                "faucet_enabled": False,
                "glm_token_address": "",
                "token_symbol": "GLM",
                "gas_symbol": "ETH",
            },
            "hoodi": {
                "rpc_url": "https://rpc.hoodi.ethpandaops.io",
                "ws_url": "wss://ethereum-hoodi-rpc.publicnode.com",
                "faucet_enabled": False,
                "glm_token_address": "0x55555555555556AcFf9C332Ed151758858bd7a26",
                "token_symbol": "GLM",
                "gas_symbol": "ETH",
            },
            "mainnet": {
                "rpc_url": "",
                "ws_url": "",
                "faucet_enabled": False,
                "glm_token_address": "",
                "token_symbol": "GLM",
                "gas_symbol": "ETH",
            },
        }
        return profiles.get(n, profiles["hoodi"])

    @field_validator("STREAM_PAYMENT_ADDRESS", mode="before")
    @classmethod
    def default_stream_addr(cls, v: str, values: dict) -> str:
        # Disable payments during pytest to keep unit tests independent
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return "0x0000000000000000000000000000000000000000"
        if v:
            return v
        pn = values.data.get("PAYMENTS_NETWORK") or "hoodi"
        addr, _ = Settings._load_deployment(pn)
        return addr or "0x0000000000000000000000000000000000000000"

    @field_validator("GLM_TOKEN_ADDRESS", mode="before")
    @classmethod
    def default_token_addr(cls, v: str, values: dict) -> str:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return "0x0000000000000000000000000000000000000000"
        if v:
            return v
        pn = values.data.get("PAYMENTS_NETWORK") or "hoodi"
        _, token = Settings._load_deployment(pn)
        profile_token = str(Settings._profile_defaults(pn).get("glm_token_address", ""))
        return token or profile_token or "0x0000000000000000000000000000000000000000"

    # VM Settings
    MAX_VMS: int = 10

    # Optional human-friendly symbols from profile
    TOKEN_SYMBOL: str = Field(default="", description="Payment token symbol, e.g., GLM")
    GAS_TOKEN_SYMBOL: str = Field(default="", description="Gas token symbol, e.g., ETH")

    @field_validator("TOKEN_SYMBOL", mode="before")
    @classmethod
    def default_token_symbol(cls, v: str, values: dict) -> str:
        if v:
            return v
        pn = values.data.get("PAYMENTS_NETWORK") or "hoodi"
        return str(Settings._profile_defaults(pn).get("token_symbol", ""))

    @field_validator("GAS_TOKEN_SYMBOL", mode="before")
    @classmethod
    def default_gas_symbol(cls, v: str, values: dict) -> str:
        if v:
            return v
        pn = values.data.get("PAYMENTS_NETWORK") or "hoodi"
        return str(Settings._profile_defaults(pn).get("gas_symbol", ""))

    @property
    def FAUCET_ENABLED(self) -> bool:
        return bool(
            self._profile_defaults(self.PAYMENTS_NETWORK).get("faucet_enabled", False)
        )

    DEFAULT_VM_IMAGE: str = "24.04"
    VM_DATA_DIR: str = ""
    SSH_KEY_DIR: str = ""
    CLOUD_INIT_DIR: str = ""
    CLOUD_INIT_FALLBACK_DIR: str = ""  # Will be set to a temp directory if needed

    @field_validator("CLOUD_INIT_DIR", mode="before")
    def resolve_cloud_init_dir(cls, v: str) -> str:
        """Resolve and create cloud-init directory path."""
        import platform
        import tempfile

        from .utils.setup import (
            check_setup_needed,
            mark_setup_complete,
            setup_cloud_init_dir,
        )

        def verify_dir_permissions(path: Path) -> bool:
            """Verify directory has correct permissions and is accessible."""
            try:
                # Create test file
                test_file = path / "permission_test"
                test_file.write_text("test")
                test_file.unlink()
                return True
            except Exception:
                return False

        if v:
            path = Path(v)
            if not path.is_absolute():
                path = Path.home() / path
        else:
            system = platform.system().lower()
            # Try OS-specific paths first
            if system == "linux" and Path("/snap/bin/multipass").exists():
                # Linux with snap
                path = Path("/var/snap/multipass/common/cloud-init")

                # Check if we need to set up permissions
                if check_setup_needed():
                    logger.info(
                        "First run detected, setting up cloud-init directory..."
                    )
                    success, error = setup_cloud_init_dir(path)
                    if success:
                        logger.info("✓ Cloud-init directory setup complete")
                        mark_setup_complete()
                    else:
                        logger.error(f"Failed to set up cloud-init directory: {error}")
                        logger.error("\nTo fix this manually, run these commands:")
                        logger.error(
                            "  sudo mkdir -p /var/snap/multipass/common/cloud-init"
                        )
                        logger.error(
                            "  sudo chown -R $USER:$USER /var/snap/multipass/common/cloud-init"
                        )
                        logger.error(
                            "  sudo chmod -R 755 /var/snap/multipass/common/cloud-init\n"
                        )
                        # Fall back to user's home directory
                        path = (
                            Path.home()
                            / ".local"
                            / "share"
                            / "golem"
                            / "provider"
                            / "cloud-init"
                        )

            elif system == "linux":
                # Linux without snap
                path = (
                    Path.home()
                    / ".local"
                    / "share"
                    / "golem"
                    / "provider"
                    / "cloud-init"
                )
            elif system == "darwin":
                # macOS
                path = (
                    Path.home()
                    / "Library"
                    / "Application Support"
                    / "golem"
                    / "provider"
                    / "cloud-init"
                )
            elif system == "windows":
                # Windows
                path = (
                    Path(os.path.expandvars("%LOCALAPPDATA%"))
                    / "golem"
                    / "provider"
                    / "cloud-init"
                )
            else:
                path = Path.home() / ".golem" / "provider" / "cloud-init"

        try:
            # Try to create and verify the directory
            path.mkdir(parents=True, exist_ok=True)
            if platform.system().lower() != "windows":
                path.chmod(
                    0o755
                )  # Readable and executable by owner and others, writable by owner

            if verify_dir_permissions(path):
                logger.debug(f"Created cloud-init directory at {path}")
                return str(path)

            # If verification fails, fall back to temp directory
            fallback_path = Path(tempfile.gettempdir()) / "golem" / "cloud-init"
            fallback_path.mkdir(parents=True, exist_ok=True)
            if platform.system().lower() != "windows":
                fallback_path.chmod(0o755)

            if verify_dir_permissions(fallback_path):
                logger.warning(
                    f"Using fallback cloud-init directory at {fallback_path}"
                )
                return str(fallback_path)

            raise ValueError("Could not create a writable cloud-init directory")

        except Exception as e:
            logger.error(f"Failed to create cloud-init directory at {path}: {e}")
            raise ValueError(f"Failed to create cloud-init directory: {e}")

    @field_validator("VM_DATA_DIR", mode="before")
    def resolve_vm_data_dir(cls, v: str) -> str:
        """Resolve and create VM data directory path."""
        if not v:
            path = Path.home() / ".golem" / "provider" / "vms"
        else:
            path = Path(v)
            if not path.is_absolute():
                path = Path.home() / path

        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created VM data directory at {path}")
        except Exception as e:
            logger.error(f"Failed to create VM data directory at {path}: {e}")
            raise ValueError(f"Failed to create VM data directory: {e}")

        return str(path)

    @field_validator("SSH_KEY_DIR", mode="before")
    def resolve_ssh_key_dir(cls, v: str) -> str:
        """Resolve and create SSH key directory path with secure permissions."""
        if not v:
            path = Path.home() / ".golem" / "provider" / "ssh"
        else:
            path = Path(v)
            if not path.is_absolute():
                path = Path.home() / path

        try:
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)  # Secure permissions for SSH keys
            logger.debug(f"Created SSH key directory at {path} with secure permissions")
        except Exception as e:
            logger.error(f"Failed to create SSH key directory at {path}: {e}")
            raise ValueError(f"Failed to create SSH key directory: {e}")

        return str(path)

    # Resource Settings
    MIN_MEMORY_GB: int = 1
    MIN_STORAGE_GB: int = 10
    MIN_CPU_CORES: int = 1
    OFFERED_CPU_CORES: int = Field(default=0, ge=0)
    OFFERED_MEMORY_GB: int = Field(default=0, ge=0)
    OFFERED_STORAGE_GB: int = Field(default=0, ge=0)

    # Resource Thresholds (%)
    CPU_THRESHOLD: int = 90
    MEMORY_THRESHOLD: int = 85
    STORAGE_THRESHOLD: int = 90

    # Monitoring settings
    MONITORING_ENABLED: bool = True
    MONITORING_SAMPLE_INTERVAL_SECONDS: int = Field(default=30, ge=5)
    MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS: int = Field(default=1, ge=1)
    MONITORING_LIVE_IDLE_INTERVAL_SECONDS: int = Field(default=30, ge=5)
    MONITORING_LIVE_DISCONNECT_GRACE_SECONDS: int = Field(default=60, ge=0)
    MONITORING_HISTORY_DOWNSAMPLE_SECONDS: int = Field(default=10, ge=1)
    MONITORING_RETENTION_DAYS: int = Field(default=30, ge=1)
    MONITORING_GUEST_AGENT_DEFAULT: bool = True
    VM_AGENT_STATE_STALE_SECONDS: int = Field(default=90, ge=1)
    MONITORING_PROMETHEUS_ENABLED: bool = True
    MONITORING_OTLP_ENDPOINT: str = ""
    MONITORING_WEBHOOK_TIMEOUT_SECONDS: int = Field(default=5, ge=1)

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Retry/Timeout Settings (for long-running external calls)
    RETRY_ATTEMPTS: int = 5
    RETRY_DELAY_SECONDS: float = 2.0
    RETRY_BACKOFF: float = 2.0
    CREATE_VM_MAX_RETRIES: int = 15
    CREATE_VM_RETRY_DELAY_SECONDS: float = 5.0
    MULTIPASS_LAUNCH_INIT_TIMEOUT_SECONDS: int = Field(default=1, ge=1)
    LAUNCH_TIMEOUT_SECONDS: int = 300

    # Multipass Settings
    MULTIPASS_BINARY_PATH: str = Field(
        default="", description="Path to multipass binary"
    )

    @field_validator("MULTIPASS_BINARY_PATH")
    def detect_multipass_path(cls, v: str) -> str:
        """Keep optional explicit Multipass path without probing at import time."""
        return v.strip() if isinstance(v, str) else v

    # Proxy Settings
    PORT_RANGE_START: int = 50800
    PORT_RANGE_END: int = 50900
    PROXY_STATE_DIR: str = ""
    PUBLIC_IP: Optional[str] = None
    PUBLIC_ENDPOINT_MODE: str = Field(
        default="auto_ip_https",
        description="Public provider endpoint mode: auto_ip_https or disabled",
    )
    SECURE_SETUP_IN_DEVELOPMENT: bool = False
    PUBLIC_ENDPOINT_IP: str = "auto"
    PUBLIC_HTTPS_PORT: int = 443
    PUBLIC_HTTPS_INTERNAL_PORT: int = 443
    ACME_CHALLENGE_TYPE: str = "http-01"
    ACME_HTTP_PUBLIC_PORT: int = 80
    ACME_HTTP_INTERNAL_PORT: int = 80
    ACME_ENV: str = "production"
    ACME_DIRECTORY_URL: str = "https://acme-v02.api.letsencrypt.org/directory"
    ACME_PROFILE: str = "shortlived"
    ACME_ACCOUNT_EMAIL: str = ""
    CERT_DIR: str = ""
    CERT_RENEW_BEFORE_HOURS: int = 48
    CERT_RENEWAL_ENABLED: bool = True
    CERT_RENEWAL_CHECK_INTERVAL_SECONDS: int = 3600
    CERT_RENEWAL_RETRY_INITIAL_SECONDS: int = 300
    CERT_RENEWAL_RETRY_MAX_SECONDS: int = 21600
    NAT_AUTO_MAPPING_ENABLED: bool = False
    PORT_CHECK_TLS_URL: str = ""
    PORT_CHECK_REQUEST_TIMEOUT: float = 8.0

    @field_validator("PORT_CHECK_TLS_URL", mode="before")
    @classmethod
    def default_port_check_tls_url(cls, v: str, values: dict) -> str:
        if v:
            return str(v).rstrip("/")
        discovery_ws_url = str(values.data.get("DISCOVERY_WS_URL") or "").strip()
        return derive_port_check_url(discovery_ws_url)

    @field_validator("ACME_ENV", mode="before")
    @classmethod
    def normalize_acme_environment(cls, v: str) -> str:
        return normalize_acme_env(v)

    @field_validator("ACME_DIRECTORY_URL", mode="before")
    @classmethod
    def resolve_acme_directory_url(cls, v: str, values: dict) -> str:
        if os.environ.get("GOLEM_PROVIDER_ACME_DIRECTORY_URL"):
            return v
        env = normalize_acme_env(str(values.data.get("ACME_ENV") or "production"))
        if env == "staging":
            return "https://acme-staging-v02.api.letsencrypt.org/directory"
        return v or "https://acme-v02.api.letsencrypt.org/directory"

    @field_validator("PROXY_STATE_DIR", mode="before")
    def resolve_proxy_state_dir(cls, v: str) -> str:
        """Resolve and create proxy state directory path."""
        if not v:
            path = Path.home() / ".golem" / "provider" / "proxy"
        else:
            path = Path(v)
            if not path.is_absolute():
                path = Path.home() / path

        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created proxy state directory at {path}")
        except Exception as e:
            logger.error(f"Failed to create proxy state directory at {path}: {e}")
            raise ValueError(f"Failed to create proxy state directory: {e}")

        return str(path)

    @field_validator("CERT_DIR", mode="before")
    def resolve_cert_dir(cls, v: str) -> str:
        """Resolve and create certificate storage directory."""
        if not v:
            path = Path.home() / ".golem" / "provider" / "certs"
        else:
            path = Path(v)
            if not path.is_absolute():
                path = Path.home() / path

        try:
            path.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                path.chmod(0o700)
        except Exception as e:
            logger.error(f"Failed to create certificate directory at {path}: {e}")
            raise ValueError(f"Failed to create certificate directory: {e}")

        return str(path)

    # Pricing Settings (configured in USD)
    # Per-month prices per unit
    PRICE_USD_PER_CORE_MONTH: float = Field(default=5.0, ge=0)
    PRICE_USD_PER_GB_RAM_MONTH: float = Field(default=2.0, ge=0)
    PRICE_USD_PER_GB_STORAGE_MONTH: float = Field(default=0.1, ge=0)

    # Auto-updated GLM-denominated prices (derived from USD via CoinGecko)
    PRICE_GLM_PER_CORE_MONTH: float = Field(default=0.0, ge=0)
    PRICE_GLM_PER_GB_RAM_MONTH: float = Field(default=0.0, ge=0)
    PRICE_GLM_PER_GB_STORAGE_MONTH: float = Field(default=0.0, ge=0)

    # CoinGecko integration
    COINGECKO_API_URL: str = "https://api.coingecko.com/api/v3"
    COINGECKO_IDS: str = "golem,golem-network-tokens"  # try both, first wins
    PRICING_UPDATE_ENABLED: bool = True
    PRICING_UPDATE_MIN_DELTA_PERCENT: float = Field(default=1.0, ge=0.0)
    PRICING_UPDATE_INTERVAL_DISCOVERY: int = 900  # 15 minutes

    class Config:
        env_prefix = "GOLEM_PROVIDER_"
        case_sensitive = True


# Global settings instance
settings = Settings()
