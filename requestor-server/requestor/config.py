from pathlib import Path
from typing import Optional, Dict
from pydantic_settings import BaseSettings
from pydantic import Field, validator

class RequestorConfig(BaseSettings):
    """Configuration settings for the requestor node."""
    
    class Config:
        env_prefix = "GOLEM_REQUESTOR_"
    
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

    @validator("discovery_url", always=True)
    def set_discovery_url(cls, v: str, values: dict) -> str:
        """Prefix discovery URL with DEVMODE if in development."""
        if values.get("environment") == "development":
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
        default_factory=lambda: Path.home() / ".golem",
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
        # Set dependent paths before validation
        if 'ssh_key_dir' not in kwargs:
            base_dir = kwargs.get('base_dir', Path.home() / ".golem")
            kwargs['ssh_key_dir'] = base_dir / "ssh"
        if 'db_path' not in kwargs:
            base_dir = kwargs.get('base_dir', Path.home() / ".golem")
            kwargs['db_path'] = base_dir / "vms.db"
        super().__init__(**kwargs)

    def get_provider_url(self, ip_address: str) -> str:
        """Get provider API URL.
        
        Args:
            ip_address: The IP address of the provider.
        
        Returns:
            The complete provider URL with protocol and port.
        """
        if self.environment == "development" and self.force_localhost:
            return "http://localhost:7466"
        return f"http://{ip_address}:7466"

config = RequestorConfig()
