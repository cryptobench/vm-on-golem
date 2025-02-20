import yaml
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..config import settings
from ..utils.logging import setup_logger

logger = setup_logger(__name__)

def validate_cloud_init(content: str) -> bool:
    """Validate cloud-init configuration content.
    
    Args:
        content: YAML content to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # First validate YAML syntax
        yaml.safe_load(content)
        
        # Check for required #cloud-config header
        if not content.startswith("#cloud-config\n"):
            logger.error("Cloud-init config missing #cloud-config header")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Cloud-init validation failed: {e}")
        return False

def generate_cloud_init(
    hostname: str,
    ssh_key: str,
    packages: Optional[list[str]] = None,
    runcmd: Optional[list[str]] = None
) -> Tuple[str, str]:
    """Generate cloud-init configuration.
    
    Args:
        hostname: VM hostname
        ssh_key: SSH public key to add to authorized_keys
        packages: List of packages to install
        runcmd: List of commands to run on first boot
    
    Returns:
        Tuple of (path to cloud-init configuration file, config_id for debugging)
    """
    # Generate unique config ID for this cloud-init file
    config_id = f"{hostname}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    config_path = Path(settings.CLOUD_INIT_DIR) / f"{config_id}.yaml"
    
    logger.info(f"Generating cloud-init configuration {config_id}")
    try:
        # Start with required #cloud-config header
        yaml_content = "#cloud-config\n"
        
        config = {
            "version": 1,
            "hostname": hostname,
            "package_update": True,
            "package_upgrade": True,
            "preserve_hostname": False,
            "ssh_authorized_keys": [ssh_key],
            "users": [{
                "name": "root",
                "ssh_authorized_keys": [ssh_key]
            }],
            "write_files": [
                {
                    "path": "/etc/ssh/sshd_config.d/allow_root.conf",
                    "content": "PermitRootLogin prohibit-password\n",
                    "owner": "root:root",
                    "permissions": "0644"
                }
            ],
            "runcmd": [
                "systemctl restart ssh"
            ]
        }

        if packages:
            config["packages"] = packages

        if runcmd:
            config["runcmd"].extend(runcmd)

        # Add config to YAML content with document markers
        yaml_content += "---\n"
        yaml_content += yaml.safe_dump(config, default_flow_style=False, sort_keys=False)

        # Validate the configuration
        if not validate_cloud_init(yaml_content):
            raise Exception("Cloud-init configuration validation failed")

        # Write to file in our managed directory
        with open(config_path, 'w') as f:
            f.write(yaml_content)
        
        # Set proper permissions
        if os.name != 'nt':  # Skip on Windows
            config_path.chmod(0o644)  # World readable but only owner writable
        
        logger.debug(f"Cloud-init configuration written to {config_path}")
        logger.debug(f"Cloud-init configuration content:\n{yaml_content}")
        
        return str(config_path), config_id

    except Exception as e:
        error_msg = f"Failed to generate cloud-init configuration: {str(e)}"
        logger.error(f"{error_msg}\nConfig ID: {config_id}")
        # Don't cleanup on error - keep file for debugging
        if config_path.exists():
            logger.info(f"Failed config preserved at {config_path} for debugging")
            # Log the file contents for debugging
            try:
                logger.debug(f"Failed config contents:\n{config_path.read_text()}")
            except Exception as read_error:
                logger.error(f"Could not read failed config: {read_error}")
        raise Exception(error_msg)

def cleanup_cloud_init(path: str, config_id: str) -> None:
    """Clean up cloud-init configuration file.
    
    Args:
        path: Path to cloud-init configuration file
        config_id: Configuration ID for logging
    """
    try:
        Path(path).unlink()
        logger.debug(f"Cleaned up cloud-init configuration {config_id}")
    except Exception as e:
        logger.warning(f"Failed to cleanup cloud-init configuration {config_id}: {e}")
