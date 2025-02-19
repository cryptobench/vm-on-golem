import os
from pathlib import Path
from typing import Optional
import uuid

from pydantic import BaseSettings, validator

class Settings(BaseSettings):
    """Provider configuration settings."""
    
    # API Settings
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 7466
    
    # Provider Settings
    PROVIDER_ID: str = str(uuid.uuid4())  # Default to random UUID if not set
    PROVIDER_NAME: str = "golem-provider"
    PROVIDER_COUNTRY: str = "SE"
    
    # Discovery Service Settings
    DISCOVERY_URL: str = "http://localhost:7465"
    ADVERTISEMENT_INTERVAL: int = 240  # seconds
    
    # VM Settings
    MAX_VMS: int = 10
    DEFAULT_VM_IMAGE: str = "ubuntu:20.04"
    VM_DATA_DIR: str = str(Path.home() / ".golem" / "provider" / "vms")
    SSH_KEY_DIR: str = str(Path.home() / ".golem" / "provider" / "ssh")
    
    # Resource Settings
    MIN_MEMORY_GB: int = 1
    MIN_STORAGE_GB: int = 10
    MIN_CPU_CORES: int = 1
    
    # Resource Thresholds (%)
    CPU_THRESHOLD: int = 90
    MEMORY_THRESHOLD: int = 85
    STORAGE_THRESHOLD: int = 90
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Multipass Settings
    MULTIPASS_PATH: str = "/usr/local/bin/multipass"
    
    # Nginx Settings
    NGINX_DIR: str = "/opt/homebrew/etc/nginx"
    NGINX_CONFIG_DIR: Optional[str] = None
    PORT_RANGE_START: int = 50800
    PORT_RANGE_END: int = 50900
    PUBLIC_IP: Optional[str] = None
    
    @validator("NGINX_CONFIG_DIR", pre=True, always=True)
    def set_nginx_config_dir(cls, v: Optional[str], values: dict) -> str:
        """Set nginx config directory if not provided."""
        if v is None:
            return os.path.join(values["NGINX_DIR"], "golem.d")
        return v
    
    @validator("PUBLIC_IP", pre=True)
    def get_public_ip(cls, v: Optional[str]) -> Optional[str]:
        """Get public IP if set to 'auto'."""
        if v == "auto":
            try:
                import requests
                response = requests.get("https://api.ipify.org")
                return response.text.strip()
            except Exception:
                return None
        return v
    
    class Config:
        env_prefix = "GOLEM_PROVIDER_"
        case_sensitive = True

# Global settings instance
settings = Settings()
