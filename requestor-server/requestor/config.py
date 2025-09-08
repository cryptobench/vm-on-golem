from pathlib import Path
from typing import Optional, Dict
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, ValidationInfo


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
