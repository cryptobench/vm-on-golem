from pydantic import BaseSettings, validator, DirectoryPath
from typing import Optional
from pathlib import Path
import secrets
import platform

class Settings(BaseSettings):
    # Provider Settings
    PROVIDER_ID: str = "provider123"  # Default for development
    PROVIDER_NAME: str = "golem-provider"
    COUNTRY: str = "SE"  # ISO 3166-1 alpha-2

    # Discovery Service Settings
    DISCOVERY_URL: str = "http://discovery.golem.network:7465"
    ADVERTISEMENT_INTERVAL: int = 240  # 4 minutes

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "VM on Golem Provider Node"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 7465

    # VM Settings
    MAX_VMS: int = 10
    DEFAULT_VM_IMAGE: str = "ubuntu:20.04"
    VM_DATA_DIR: DirectoryPath = Path.home() / ".golem" / "provider" / "vms"
    
    # Multipass Settings
    MULTIPASS_PATH: str = ""
    
    @validator("MULTIPASS_PATH", pre=True)
    def set_multipass_path(cls, v: Optional[str]) -> str:
        """Set the multipass path based on the OS if not provided."""
        if v:
            return v
            
        system = platform.system()
        if system == "Darwin":  # macOS
            return "/usr/local/bin/multipass"
        elif system == "Linux":
            return "/usr/bin/multipass"
        elif system == "Windows":
            return r"C:\Program Files\Multipass\bin\multipass.exe"
        else:
            raise ValueError(f"Unsupported operating system: {system}")

    @validator("VM_DATA_DIR")
    def create_vm_data_dir(cls, v: Path) -> Path:
        """Create VM data directory if it doesn't exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    # Security Settings
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SSH_KEY_DIR: DirectoryPath = Path.home() / ".golem" / "provider" / "ssh"
    
    @validator("SSH_KEY_DIR")
    def create_ssh_key_dir(cls, v: Path) -> Path:
        """Create SSH key directory if it doesn't exist."""
        v.mkdir(parents=True, exist_ok=True)
        # Set proper permissions (700)
        v.chmod(0o700)
        return v

    # Resource Settings
    MIN_MEMORY_GB: int = 1
    MIN_STORAGE_GB: int = 10
    MIN_CPU_CORES: int = 1
    
    # Resource Thresholds (percentage)
    CPU_THRESHOLD: int = 90  # Don't accept new VMs if CPU usage > 90%
    MEMORY_THRESHOLD: int = 85  # Don't accept new VMs if memory usage > 85%
    STORAGE_THRESHOLD: int = 90  # Don't accept new VMs if storage usage > 90%
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100  # Maximum requests per minute per IP

    class Config:
        case_sensitive = True
        env_prefix = "GOLEM_PROVIDER_"

settings = Settings()
