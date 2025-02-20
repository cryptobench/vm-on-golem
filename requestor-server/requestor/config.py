from pathlib import Path
from typing import Optional, Dict
from pydantic import BaseSettings, Field

class RequestorConfig(BaseSettings):
    """Configuration settings for the requestor node."""
    
    # Discovery Service
    discovery_url: str = "http://localhost:7465"
    
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
        """Get provider API URL."""
        # For development, always use localhost
        return "http://localhost:7466"

config = RequestorConfig()
