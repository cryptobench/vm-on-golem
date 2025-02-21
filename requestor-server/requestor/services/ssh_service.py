"""SSH connection service."""
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from ..ssh.manager import SSHKeyManager
from ..errors import SSHError

class SSHService:
    """Service for handling SSH connections."""
    
    def __init__(self, ssh_key_dir: Path):
        self.ssh_manager = SSHKeyManager(ssh_key_dir)

    async def get_key_pair(self):
        """Get or create SSH key pair."""
        try:
            return await self.ssh_manager.get_key_pair()
        except Exception as e:
            raise SSHError(f"Failed to get SSH key pair: {str(e)}")

    def connect_to_vm(
        self,
        host: str,
        port: int,
        private_key_path: Path,
        username: str = "ubuntu"
    ) -> None:
        """Connect to VM via SSH."""
        try:
            cmd = [
                "ssh",
                "-i", str(private_key_path),
                "-p", str(port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                f"{username}@{host}"
            ]
            subprocess.run(cmd)
        except Exception as e:
            raise SSHError(f"Failed to establish SSH connection: {str(e)}")

    def format_ssh_command(
        self,
        host: str,
        port: int,
        private_key_path: Path,
        username: str = "ubuntu",
        colorize: bool = False
    ) -> str:
        """Format SSH command for display."""
        from click import style

        command = (
            f"ssh -i {private_key_path} "
            f"-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-p {port} {username}@{host}"
        )

        if colorize:
            return style(command, fg="yellow")
        return command
