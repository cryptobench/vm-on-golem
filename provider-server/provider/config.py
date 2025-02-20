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
    PROVIDER_ID: str = ""  # Will be set from Ethereum identity
    PROVIDER_NAME: str = "golem-provider"
    PROVIDER_COUNTRY: str = "SE"
    ETHEREUM_KEY_DIR: str = ""

    @validator("ETHEREUM_KEY_DIR", pre=True)
    def resolve_key_dir(cls, v: str) -> str:
        """Resolve Ethereum key directory path."""
        if not v:
            return str(Path.home() / ".golem" / "provider" / "keys")
        path = Path(v)
        if not path.is_absolute():
            path = Path.home() / path
        return str(path)

    @validator("PROVIDER_ID", always=True)
    def get_or_create_provider_id(cls, v: str, values: dict) -> str:
        """Get or create provider ID from Ethereum identity."""
        from provider.security.ethereum import EthereumIdentity

        # If ID provided in env, use it
        if v:
            return v

        # Get ID from Ethereum identity
        key_dir = values.get("ETHEREUM_KEY_DIR")
        identity = EthereumIdentity(key_dir)
        return identity.get_or_create_identity()

    # Discovery Service Settings
    DISCOVERY_URL: str = "http://localhost:7465"
    ADVERTISEMENT_INTERVAL: int = 240  # seconds

    # VM Settings
    MAX_VMS: int = 10
    DEFAULT_VM_IMAGE: str = "ubuntu:24.04"
    VM_DATA_DIR: str = ""
    SSH_KEY_DIR: str = ""

    @validator("VM_DATA_DIR", pre=True)
    def resolve_vm_data_dir(cls, v: str) -> str:
        """Resolve VM data directory path."""
        if not v:
            return str(Path.home() / ".golem" / "provider" / "vms")
        path = Path(v)
        if not path.is_absolute():
            path = Path.home() / path
        return str(path)

    @validator("SSH_KEY_DIR", pre=True)
    def resolve_ssh_key_dir(cls, v: str) -> str:
        """Resolve SSH key directory path."""
        if not v:
            return str(Path.home() / ".golem" / "provider" / "ssh")
        path = Path(v)
        if not path.is_absolute():
            path = Path.home() / path
        return str(path)

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
    MULTIPASS_BINARY_PATH: str = ""

    @validator("MULTIPASS_BINARY_PATH", pre=True)
    def detect_multipass_path(cls, v: str) -> str:
        """Detect and validate Multipass binary path."""
        if v:
            path = v
        else:
            # Common Multipass binary locations
            binary_name = "multipass"
            search_paths = [
                "/usr/local/bin",          # Common Unix/Linux
                "/usr/bin",                # Linux
                "/opt/homebrew/bin",       # macOS M1 (Homebrew)
                "/snap/bin",               # Linux (Snap)
            ]

            # Search for multipass binary
            for directory in search_paths:
                path = os.path.join(directory, binary_name)
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path

            raise ValueError(
                "Multipass binary not found. Please install Multipass or set "
                "GOLEM_PROVIDER_MULTIPASS_BINARY_PATH to your Multipass binary path."
            )

        # Validate the path
        if not os.path.isfile(path):
            raise ValueError(f"Multipass binary not found at: {path}")
        if not os.access(path, os.X_OK):
            raise ValueError(f"Multipass binary at {path} is not executable")
        return path

    # Proxy Settings
    PORT_RANGE_START: int = 50800
    PORT_RANGE_END: int = 50900
    PROXY_STATE_DIR: str = ""
    PUBLIC_IP: Optional[str] = None

    @validator("PROXY_STATE_DIR", pre=True)
    def resolve_proxy_state_dir(cls, v: str) -> str:
        """Resolve proxy state directory path."""
        if not v:
            return str(Path.home() / ".golem" / "provider" / "proxy")
        path = Path(v)
        if not path.is_absolute():
            path = Path.home() / path
        return str(path)

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
