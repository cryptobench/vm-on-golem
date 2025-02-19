import yaml
import tempfile
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class CloudInitManager:
    @staticmethod
    def create_config(ssh_key: str) -> Path:
        """Create cloud-init config with SSH key."""
        config = {
            "users": [{
                "name": "ubuntu",
                "sudo": "ALL=(ALL) NOPASSWD:ALL",
                "shell": "/bin/bash",
                "ssh_authorized_keys": [ssh_key]
            }],
            "ssh_pwauth": False,  # Disable password authentication
            "package_update": True,  # Update package list on first boot
            "package_upgrade": True  # Upgrade packages on first boot
        }
        
        try:
            # Create temporary file for cloud-init config
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write("#cloud-config\n")  # Required header
                yaml.dump(config, f, default_flow_style=False)
                logger.info(f"Created cloud-init config at {f.name}")
                return Path(f.name)
        except Exception as e:
            logger.error(f"Failed to create cloud-init config: {e}")
            raise
