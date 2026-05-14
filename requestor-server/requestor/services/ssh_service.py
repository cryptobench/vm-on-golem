"""SSH connection service."""
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from ..errors import SSHError
from ..ssh.manager import SSHKeyManager

logger = logging.getLogger(__name__)


class SSHService:
    """Service for handling SSH connections."""

    def __init__(self, ssh_key_dir: Path):
        self.ssh_manager = SSHKeyManager(ssh_key_dir)

    async def get_key_pair(self):
        """Get or create SSH key pair."""
        try:
            key_pair = await self.ssh_manager.get_key_pair()
            logger.info("Requestor SSH key pair ready")
            return key_pair
        except Exception as e:
            logger.error("Failed to get requestor SSH key pair", exc_info=True)
            raise SSHError(f"Failed to get SSH key pair: {str(e)}")

    def get_key_pair_sync(self):
        """Get or create SSH key pair synchronously."""
        try:
            key_pair = self.ssh_manager.get_key_pair_sync()
            logger.info("Requestor SSH key pair ready")
            return key_pair
        except Exception as e:
            logger.error("Failed to get requestor SSH key pair", exc_info=True)
            raise SSHError(f"Failed to get SSH key pair: {str(e)}")

    def connect_to_vm(
        self, host: str, port: int, private_key_path: Path, username: str
    ) -> None:
        """Connect to VM via SSH."""
        try:
            cmd = [
                "ssh",
                "-i",
                str(private_key_path),
                "-p",
                str(port),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"{username}@{host}",
            ]
            logger.info("Opening SSH connection", extra={"host": host, "port": port})
            subprocess.run(cmd, check=True)
        except Exception as e:
            logger.error(
                "Failed to establish SSH connection",
                extra={"host": host, "port": port},
                exc_info=True,
            )
            raise SSHError(f"Failed to establish SSH connection: {str(e)}")

    def format_ssh_command(
        self,
        host: str,
        port: int,
        private_key_path: Path,
        username: str,
        colorize: bool = False,
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

    def get_vm_stats(
        self, host: str, port: int, private_key_path: Path, username: str
    ) -> Dict:
        """Get VM stats via SSH."""
        try:
            cmd = [
                "ssh",
                "-i",
                str(private_key_path),
                "-p",
                str(port),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"{username}@{host}",
                "top -b -n 1; df -h /",
            ]
            logger.debug(
                "Fetching VM stats over SSH", extra={"host": host, "port": port}
            )
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return self._parse_stats(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(
                "Failed to fetch VM stats over SSH",
                extra={"host": host, "port": port},
                exc_info=True,
            )
            raise SSHError(f"Failed to get VM stats: {e.stderr}")
        except Exception as e:
            logger.error(
                "Unexpected SSH stats error",
                extra={"host": host, "port": port},
                exc_info=True,
            )
            raise SSHError(f"An unexpected error occurred: {str(e)}")

    def _parse_stats(self, stats_output: str) -> Dict:
        """Parse the output of the stats command."""
        lines = stats_output.strip().split("\n")
        stats = {"cpu": {}, "memory": {}, "disk": {}}

        for line in lines:
            if line.startswith("%Cpu(s):"):
                parts = line.split(",")
                for part in parts:
                    if "id" in part:
                        idle_str = part.strip().split()[0]
                        try:
                            idle = float(idle_str)
                            stats["cpu"]["usage"] = f"{100.0 - idle:.1f}%"
                        except ValueError:
                            stats["cpu"]["usage"] = "N/A"
                        break
            elif "MiB Mem" in line:
                parts = line.split(",")
                total_mem_str = parts[0].split(":")[1].strip().split()[0]
                used_mem_str = parts[2].strip().split()[0]
                stats["memory"] = {
                    "total": f"{float(total_mem_str):.1f} MiB",
                    "used": f"{float(used_mem_str):.1f} MiB",
                }
            elif line.startswith("/dev/"):
                parts = line.split()
                stats["disk"] = {
                    "total": parts[1],
                    "used": parts[2],
                }

        return stats
