import os
from pathlib import Path
from typing import Optional
import uuid

from pydantic import BaseSettings, validator, Field
from .utils.logging import setup_logger

logger = setup_logger(__name__)


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
    DISCOVERY_URL: str = "http://195.201.39.101:9001"
    ADVERTISEMENT_INTERVAL: int = 240  # seconds

    # VM Settings
    MAX_VMS: int = 10
    DEFAULT_VM_IMAGE: str = "ubuntu:24.04"
    VM_DATA_DIR: str = ""
    SSH_KEY_DIR: str = ""

    @validator("VM_DATA_DIR", pre=True)
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

    @validator("SSH_KEY_DIR", pre=True)
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

    # Resource Thresholds (%)
    CPU_THRESHOLD: int = 90
    MEMORY_THRESHOLD: int = 85
    STORAGE_THRESHOLD: int = 90

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Multipass Settings
    MULTIPASS_BINARY_PATH: str = Field(
        default="",
        description="Path to multipass binary"
    )

    @validator("MULTIPASS_BINARY_PATH")
    def detect_multipass_path(cls, v: str) -> str:
        """Detect and validate Multipass binary path."""
        import platform
        import subprocess
        
        def validate_path(path: str) -> bool:
            """Validate that a path exists and is executable."""
            return os.path.isfile(path) and os.access(path, os.X_OK)

        # If path provided via environment variable, ONLY validate that path
        if v:
            logger.info(f"Checking multipass binary at: {v}")
            if not validate_path(v):
                msg = f"Invalid multipass binary path: {v} (not found or not executable)"
                logger.error(msg)
                raise ValueError(msg)
            logger.info(f"✓ Found valid multipass binary at: {v}")
            return v

        logger.info("No multipass path provided, attempting auto-detection...")
        system = platform.system().lower()
        logger.info(f"Detected OS: {system}")
        binary_name = "multipass.exe" if system == "windows" else "multipass"
        
        # Try to find multipass based on OS
        if system == "linux":
            logger.info("Checking for snap installation...")
            # First try to find snap and check if multipass is installed
            try:
                # Check if snap exists
                snap_result = subprocess.run(
                    ["which", "snap"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                if snap_result.returncode == 0:
                    logger.info("✓ Found snap, checking for multipass installation...")
                    # Check if multipass is installed via snap
                    try:
                        snap_list = subprocess.run(
                            ["snap", "list", "multipass"],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        if snap_list.returncode == 0:
                            snap_path = "/snap/bin/multipass"
                            if validate_path(snap_path):
                                logger.info(f"✓ Found multipass via snap at {snap_path}")
                                return snap_path
                    except subprocess.CalledProcessError:
                        logger.info("✗ Multipass not installed via snap")
                        pass
            except subprocess.CalledProcessError:
                logger.info("✗ Snap not found")
                pass
                
            # Common Linux paths if snap installation not found
            search_paths = [
                "/usr/local/bin",
                "/usr/bin",
                "/snap/bin"
            ]
            logger.info(f"Checking common Linux paths: {', '.join(search_paths)}")
                
        elif system == "darwin":  # macOS
            search_paths = [
                "/opt/homebrew/bin",    # M1 Mac
                "/usr/local/bin",       # Intel Mac
                "/opt/local/bin"        # MacPorts
            ]
            logger.info(f"Checking macOS paths: {', '.join(search_paths)}")
                
        elif system == "windows":
            search_paths = [
                os.path.expandvars(r"%ProgramFiles%\Multipass"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Multipass"),
                os.path.expandvars(r"%LocalAppData%\Multipass")
            ]
            logger.info(f"Checking Windows paths: {', '.join(search_paths)}")
                
        else:
            search_paths = ["/usr/local/bin", "/usr/bin"]
            logger.info(f"Checking default paths: {', '.join(search_paths)}")

        # Search for multipass binary in OS-specific paths
        for directory in search_paths:
            path = os.path.join(directory, binary_name)
            if validate_path(path):
                logger.info(f"✓ Found valid multipass binary at: {path}")
                return path

        # OS-specific installation instructions
        if system == "linux":
            raise ValueError(
                "Multipass binary not found. Please install using:\n"
                "sudo snap install multipass\n"
                "Or set GOLEM_PROVIDER_MULTIPASS_BINARY_PATH to your Multipass binary path."
            )
        elif system == "darwin":
            raise ValueError(
                "Multipass binary not found. Please install using:\n"
                "brew install multipass\n"
                "Or set GOLEM_PROVIDER_MULTIPASS_BINARY_PATH to your Multipass binary path."
            )
        elif system == "windows":
            raise ValueError(
                "Multipass binary not found. Please install from:\n"
                "Microsoft Store or https://multipass.run/download/windows\n"
                "Or set GOLEM_PROVIDER_MULTIPASS_BINARY_PATH to your Multipass binary path."
            )
        else:
            raise ValueError(
                "Multipass binary not found. Please install Multipass or set "
                "GOLEM_PROVIDER_MULTIPASS_BINARY_PATH to your Multipass binary path."
            )

    # Proxy Settings
    PORT_RANGE_START: int = 50800
    PORT_RANGE_END: int = 50900
    PROXY_STATE_DIR: str = ""
    PUBLIC_IP: Optional[str] = None

    @validator("PROXY_STATE_DIR", pre=True)
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
