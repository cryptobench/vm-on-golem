from pathlib import Path
from typing import Optional, Dict
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, ValidationInfo
import os


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
        print("Using default settings – run with --help to customize")


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
        default="https://l2.holesky.golemdb.io/rpc",
        description="EVM RPC URL for streaming payments (L2 by default)"
    )
    stream_payment_address: str = Field(
        default="",
        description="Deployed StreamPayment contract address (defaults to contracts/deployments/l2.json)"
    )
    glm_token_address: str = Field(
        default="",
        description="Token address (0x0 means native ETH). Defaults from l2.json"
    )
    # Faucet settings (L2 payments)
    l2_faucet_url: str = Field(
        default="https://l2.holesky.golemdb.io/faucet",
        description="L2 faucet base URL (no trailing /api)"
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
    def prefer_alt_env(cls, v: str) -> str:
        # Accept alt aliases
        for key in (
            "GOLEM_REQUESTOR_l2_rpc_url",
            "GOLEM_REQUESTOR_L2_RPC_URL",
            "GOLEM_REQUESTOR_kaolin_rpc_url",
            "GOLEM_REQUESTOR_KAOLIN_RPC_URL",
        ):
            if os.environ.get(key):
                return os.environ[key]
        return v

    @staticmethod
    def _load_l2_deployment() -> tuple[str | None, str | None]:
        try:
            base = os.environ.get("GOLEM_DEPLOYMENTS_DIR")
            if base:
                path = Path(base) / "l2.json"
            else:
                # repo root assumption: ../../ relative to this file
                path = Path(__file__).resolve().parents[2] / "contracts" / "deployments" / "l2.json"
            if not path.exists():
                # Try package resource fallback
                try:
                    import importlib.resources as ir
                    with ir.files("requestor.data.deployments").joinpath("l2.json").open("r") as fh:  # type: ignore[attr-defined]
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

    @field_validator("stream_payment_address", mode='before')
    @classmethod
    def default_stream_addr(cls, v: str) -> str:
        if v:
            return v
        addr, _ = RequestorConfig._load_l2_deployment()
        return addr or "0x0000000000000000000000000000000000000000"

    @field_validator("glm_token_address", mode='before')
    @classmethod
    def default_token_addr(cls, v: str) -> str:
        if v:
            return v
        _, token = RequestorConfig._load_l2_deployment()
        return token or "0x0000000000000000000000000000000000000000"

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
