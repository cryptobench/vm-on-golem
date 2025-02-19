from pathlib import Path
from typing import Optional, Dict
from pydantic import BaseSettings, Field

class RequestorConfig(BaseSettings):
    """Configuration settings for the requestor node."""
    
    # Discovery Service
    discovery_url: str = "http://localhost:7465"
    
    # SSH Settings
    ssh_key_dir: Path = Field(
        default_factory=lambda: Path.home() / ".golem" / "ssh"
    )
    
    # Database Settings
    db_path: Path = Field(
        default_factory=lambda: Path.home() / ".golem" / "vms.db"
    )

    def get_provider_url(self, ip_address: str) -> str:
        """Get provider API URL."""
        # For development, always use localhost
        return "http://localhost:7466"

config = RequestorConfig()
