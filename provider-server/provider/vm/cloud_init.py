import yaml
import tempfile
from pathlib import Path
from typing import Dict, Optional

def generate_cloud_init(
    hostname: str,
    ssh_key: str,
    packages: Optional[list[str]] = None,
    runcmd: Optional[list[str]] = None
) -> str:
    """Generate cloud-init configuration.
    
    Args:
        hostname: VM hostname
        ssh_key: SSH public key to add to authorized_keys
        packages: List of packages to install
        runcmd: List of commands to run on first boot
    
    Returns:
        Path to cloud-init configuration file
    """
    config = {
        "hostname": hostname,
        "package_update": True,
        "package_upgrade": True,
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

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.safe_dump(config, temp_file)
    temp_file.close()

    return temp_file.name

def cleanup_cloud_init(path: str) -> None:
    """Clean up cloud-init configuration file.
    
    Args:
        path: Path to cloud-init configuration file
    """
    try:
        Path(path).unlink()
    except Exception:
        pass
