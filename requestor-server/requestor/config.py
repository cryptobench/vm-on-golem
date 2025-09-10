from pathlib import Path
from typing import Optional, Dict
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, ValidationInfo
import os
import sys


def ensure_config() -> None:
    """Ensure the requestor configuration directory and defaults exist."""
    base_dir = Path.home() / ".golem" / "requestor"
    ssh_dir = base_dir / "ssh"
    env_file = base_dir / ".env"
    created = False

    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)
        created = True
    if not ssh_dir.exists():
        ssh_dir.mkdir(parents=True, exist_ok=True)
        created = True

    if not env_file.exists():
        env_file.write_text("GOLEM_REQUESTOR_ENVIRONMENT=production\n")
        created = True

    private_key = ssh_dir / "id_rsa"
    public_key = ssh_dir / "id_rsa.pub"
    if not private_key.exists():
        private_key.write_text("placeholder-private-key")
        private_key.chmod(0o600)
        public_key.write_text("placeholder-public-key")
        created = True

    if created:
        # Write to stderr so stdout stays clean for JSON outputs
        print("Using default settings – run with --help to customize", file=sys.stderr)


ensure_config()

class RequestorConfig(BaseSettings):
    """Configuration settings for the requestor node."""

    model_config = SettingsConfigDict(env_prefix="GOLEM_REQUESTOR_")
    
    # Environment
    environment: str = Field(
        default="production",
        description="Environment mode: 'development' or 'production'"
    )
    # Network (for discovery filtering and defaults)
    network: str = Field(
        default="mainnet",
        description="Target network: 'testnet' or 'mainnet'"
    )
    
    # Payments chain selection (modular network profiles)
    # Keep current standard as l2.holesky
    payments_network: str = Field(
        default="l2.holesky",
        description="Payments network profile (e.g., 'l2.holesky', 'kaolin.holesky', 'mainnet')"
    )
    
    # Development Settings
    force_localhost: bool = Field(
        default=False,
        description="Force localhost for provider URLs in development mode"
    )

    @property
    def DEV_MODE(self) -> bool:
        return self.environment == "development"
    
    # Discovery Service
    discovery_driver: str = Field(
        default="golem-base",
        description="Discovery driver: 'central' or 'golem-base'"
    )
    discovery_url: str = Field(
        default="http://195.201.39.101:9001",
        description="URL of the discovery service (for 'central' driver)"
    )

    @field_validator("discovery_url")
    @classmethod
    def set_discovery_url(cls, v: str, info: ValidationInfo) -> str:
        """Prefix discovery URL with DEVMODE if in development."""
        if info.data.get("environment") == "development":
            return f"DEVMODE-{v}"
        return v

    # Golem Base Settings
    golem_base_rpc_url: str = Field(
        default="https://ethwarsaw.holesky.golemdb.io/rpc",
        description="Golem Base RPC URL"
    )
    golem_base_ws_url: str = Field(
        default="wss://ethwarsaw.holesky.golemdb.io/rpc/ws",
        description="Golem Base WebSocket URL"
    )
    advertisement_interval: int = Field(
        default=240,
        description="Advertisement interval in seconds (should match provider)"
    )
    ethereum_private_key: str = Field(
        default="0x0000000000000000000000000000000000000000000000000000000000000001",
        description="Private key for Golem Base"
    )
    
    # Payments (EVM RPC)
    polygon_rpc_url: str = Field(
        default="",
        description="EVM RPC URL for streaming payments; defaults from payments_network profile"
    )
    stream_payment_address: str = Field(
        default="",
        description="Deployed StreamPayment contract address (defaults to contracts/deployments/l2.json)"
    )
    glm_token_address: str = Field(
        default="",
        description="Token address (0x0 means native ETH). Defaults from l2.json"
    )
    # Stream monitor (auto top-up)
    stream_monitor_enabled: bool = Field(
        default=True,
        description="Enable background monitor to auto top-up streams"
    )
    stream_monitor_interval_seconds: int = Field(
        default=30,
        description="How frequently to check and top up streams"
    )
    stream_min_remaining_seconds: int = Field(
        default=3600,
        description="Minimum remaining runway to maintain (seconds)"
    )
    stream_topup_target_seconds: int = Field(
        default=3600,
        description="Target runway after top-up (seconds)"
    )
    # Faucet settings (payments)
    l2_faucet_url: str = Field(
        default="",
        description="Faucet base URL (no trailing /api). Only used on testnets. Defaults from payments_network profile"
    )
    captcha_url: str = Field(
        default="https://cap.gobas.me",
        description="CAPTCHA base URL"
    )
    captcha_api_key: str = Field(
        default="05381a2cef5e",
        description="CAPTCHA API key path segment"
    )
    provider_eth_address: str = Field(
        default="",
        description="Optional provider Ethereum address for test/dev streaming"
    )

    @field_validator("polygon_rpc_url", mode='before')
    @classmethod
    def prefer_alt_env(cls, v: str, info: ValidationInfo) -> str:
        # Accept alt aliases overriding the profile
        for key in (
            "GOLEM_REQUESTOR_l2_rpc_url",
            "GOLEM_REQUESTOR_L2_RPC_URL",
            "GOLEM_REQUESTOR_kaolin_rpc_url",
            "GOLEM_REQUESTOR_KAOLIN_RPC_URL",
        ):
            if os.environ.get(key):
                return os.environ[key]
        if v:
            return v
        # Default from payments profile
        pn = info.data.get("payments_network") or "l2.holesky"
        return RequestorConfig._profile_defaults(pn)["rpc_url"]

    @field_validator("l2_faucet_url", mode='before')
    @classmethod
    def default_faucet_env(cls, v: str, info: ValidationInfo) -> str:
        for key in (
            "GOLEM_REQUESTOR_l2_faucet_url",
            "GOLEM_REQUESTOR_L2_FAUCET_URL",
        ):
            if os.environ.get(key):
                return os.environ[key]
        if v:
            return v
        pn = info.data.get("payments_network") or "l2.holesky"
        return RequestorConfig._profile_defaults(pn).get("faucet_url", "")

    @staticmethod
    def _load_deployment(network: str) -> tuple[str | None, str | None]:
        try:
            base = os.environ.get("GOLEM_DEPLOYMENTS_DIR")
            if base:
                path = Path(base) / f"{RequestorConfig._deployment_basename(network)}.json"
            else:
                # repo root assumption: ../../ relative to this file
                path = (
                    Path(__file__).resolve().parents[2]
                    / "contracts" / "deployments" / f"{RequestorConfig._deployment_basename(network)}.json"
                )
            if not path.exists():
                # Try package resource fallback
                try:
                    import importlib.resources as ir
                    with ir.files("requestor.data.deployments").joinpath(
                        f"{RequestorConfig._deployment_basename(network)}.json"
                    ).open("r") as fh:  # type: ignore[attr-defined]
                        import json as _json
                        data = _json.load(fh)
                except Exception:
                    return None, None
            else:
                import json as _json
                data = _json.loads(path.read_text())
            sp = data.get("StreamPayment", {})
            addr = sp.get("address")
            token = sp.get("glmToken")
            if isinstance(addr, str) and addr:
                return addr, token or "0x0000000000000000000000000000000000000000"
        except Exception:
            pass
        return None, None

    @staticmethod
    def _deployment_basename(network: str) -> str:
        # Map well-known network aliases to deployment file base names
        n = (network or "").lower()
        if n in ("l2", "l2.holesky"):  # current standard
            return "l2"
        if "." in n:
            return n.split(".")[0]
        return n or "l2"

    @staticmethod
    def _profile_defaults(network: str) -> Dict[str, str]:
        n = (network or "l2.holesky").lower()
        # Built-in profiles; extend easily in future
        profiles = {
            "l2.holesky": {
                "rpc_url": "https://l2.holesky.golemdb.io/rpc",
                "faucet_url": "https://l2.holesky.golemdb.io/faucet",
                "faucet_enabled": True,
                "token_symbol": "GLM",
                "gas_symbol": "ETH",
            },
            # Example: mainnet has no faucet by default
            "mainnet": {
                "rpc_url": "",
                "faucet_url": "",
                "faucet_enabled": False,
                "token_symbol": "GLM",
                "gas_symbol": "ETH",
            },
        }
        return profiles.get(n, profiles["l2.holesky"])  # default to current standard

    @field_validator("stream_payment_address", mode='before')
    @classmethod
    def default_stream_addr(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        network = info.data.get("payments_network") or "l2.holesky"
        addr, _ = RequestorConfig._load_deployment(network)
        return addr or "0x0000000000000000000000000000000000000000"

    @field_validator("glm_token_address", mode='before')
    @classmethod
    def default_token_addr(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        network = info.data.get("payments_network") or "l2.holesky"
        _, token = RequestorConfig._load_deployment(network)
        return token or "0x0000000000000000000000000000000000000000"

    # Optional convenience: expose token and gas symbols based on profile
    token_symbol: str = Field(
        default="",
        description="Human-friendly symbol of payment token (e.g., GLM)"
    )
    gas_token_symbol: str = Field(
        default="",
        description="Symbol of gas token for the chain (e.g., ETH)"
    )

    @field_validator("token_symbol", mode="before")
    @classmethod
    def default_token_symbol(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        pn = info.data.get("payments_network") or "l2.holesky"
        return RequestorConfig._profile_defaults(pn).get("token_symbol", "")

    @field_validator("gas_token_symbol", mode="before")
    @classmethod
    def default_gas_symbol(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        pn = info.data.get("payments_network") or "l2.holesky"
        return RequestorConfig._profile_defaults(pn).get("gas_symbol", "")

    # Base Directory
    base_dir: Path = Field(
        default_factory=lambda: Path.home() / ".golem" / "requestor",
        description="Base directory for all Golem requestor files"
    )
    
    # SSH Settings
    ssh_key_dir: Path = Field(
        default=None,
        description="Directory for SSH keys. Defaults to {base_dir}/ssh"
    )
    
    # Database Settings
    db_path: Path = Field(
        default=None,
        description="Path to SQLite database. Defaults to {base_dir}/vms.db"
    )

    def __init__(self, **kwargs):
        # Allow overriding to dev mode with golem_dev_mode
        if os.environ.get('golem_dev_mode', 'false').lower() in ('true', '1', 't'):
            kwargs['environment'] = "development"

        # Set dependent paths before validation
        if 'ssh_key_dir' not in kwargs:
            base_dir = kwargs.get('base_dir', Path.home() / ".golem" / "requestor")
            kwargs['ssh_key_dir'] = base_dir / "ssh"
        if 'db_path' not in kwargs:
            base_dir = kwargs.get('base_dir', Path.home() / ".golem" / "requestor")
            kwargs['db_path'] = base_dir / "vms.db"
        super().__init__(**kwargs)

    @property
    def faucet_enabled(self) -> bool:
        """Whether requesting funds from faucet is allowed for current payments network."""
        return bool(self._profile_defaults(self.payments_network).get("faucet_enabled", False))

    def get_provider_url(self, ip_address: str) -> str:
        """Get provider API URL.
        
        Args:
            ip_address: The IP address of the provider.
        
        Returns:
            The complete provider URL with protocol and port.
        """
        if self.environment == "development":
            # In dev mode, we might still want to use the real IP
            pass
        return f"http://{ip_address}:7466"

config = RequestorConfig()
