import os
import subprocess
import platform
from pathlib import Path
from typing import Tuple

from .logging import setup_logger

logger = setup_logger(__name__)

def run_sudo_command(cmd: str) -> Tuple[bool, str]:
    """Run a command with sudo.
    
    Args:
        cmd: Command to run
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Try non-interactive sudo first
        result = subprocess.run(
            f"sudo -n {cmd}",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True, ""
            
        # If that fails, try interactive sudo
        logger.warning("Non-interactive sudo failed, will prompt for password")
        result = subprocess.run(
            f"sudo {cmd}",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True, ""
            
        return False, result.stderr
        
    except Exception as e:
        return False, str(e)

def setup_cloud_init_dir(path: Path) -> Tuple[bool, str]:
    """Set up cloud-init directory with correct permissions.
    
    Args:
        path: Path to cloud-init directory
        
    Returns:
        Tuple of (success, error_message)
    """
    if platform.system().lower() != "linux" or not Path("/snap/bin/multipass").exists():
        # Only needed for Linux with snap
        return True, ""
        
    try:
        # Create directory
        success, error = run_sudo_command(f"mkdir -p {path}")
        if not success:
            return False, f"Failed to create directory: {error}"
            
        # Set ownership
        user = os.environ.get("USER", os.environ.get("USERNAME"))
        success, error = run_sudo_command(f"chown -R {user}:{user} {path}")
        if not success:
            return False, f"Failed to set ownership: {error}"
            
        # Set permissions
        success, error = run_sudo_command(f"chmod -R 755 {path}")
        if not success:
            return False, f"Failed to set permissions: {error}"
            
        return True, ""
        
    except Exception as e:
        return False, str(e)

def check_setup_needed() -> bool:
    """Check if setup is needed.
    
    Returns:
        True if setup is needed, False otherwise
    """
    # Only needed for Linux with snap
    if platform.system().lower() != "linux" or not Path("/snap/bin/multipass").exists():
        return False
        
    # Check if setup has already been completed
    setup_flag = Path.home() / ".golem" / "provider" / ".setup-complete"
    return not setup_flag.exists()

def mark_setup_complete() -> None:
    """Mark setup as complete."""
    setup_flag = Path.home() / ".golem" / "provider" / ".setup-complete"
    setup_flag.parent.mkdir(parents=True, exist_ok=True)
    setup_flag.touch()
