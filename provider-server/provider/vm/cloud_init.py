import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

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
    runcmd: Optional[list[str]] = None,
    monitoring_vm_id: Optional[str] = None,
    monitoring_token: Optional[str] = None,
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

        write_files = []
        run_commands = []

        if (
            monitoring_vm_id
            and monitoring_token
            and settings.MONITORING_GUEST_AGENT_DEFAULT
        ):
            write_files.extend(
                _monitoring_agent_files(monitoring_vm_id, monitoring_token)
            )
            run_commands.extend(
                [
                    "systemctl daemon-reload",
                    "systemctl enable --now golem-metrics-agent.service",
                ]
            )

        config = {
            "version": 1,
            "hostname": hostname,
            "package_update": True,
            "package_upgrade": True,
            "preserve_hostname": False,
            "ssh_authorized_keys": [ssh_key],
            "users": ["default"],
        }

        if write_files:
            config["write_files"] = write_files

        if run_commands:
            config["runcmd"] = run_commands

        if packages:
            config["packages"] = packages

        if runcmd:
            config.setdefault("runcmd", []).extend(runcmd)

        # Add config to YAML content with document markers
        yaml_content += "---\n"
        yaml_content += yaml.safe_dump(
            config, default_flow_style=False, sort_keys=False
        )

        # Validate the configuration
        if not validate_cloud_init(yaml_content):
            raise Exception("Cloud-init configuration validation failed")

        # Write to file in our managed directory
        with open(config_path, "w") as f:
            f.write(yaml_content)

        # Set proper permissions
        if os.name != "nt":  # Skip on Windows
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


def _monitoring_agent_files(vm_id: str, token: str) -> list[dict[str, str]]:
    """Return cloud-init write_files entries for the push-only guest metrics agent."""

    port = settings.PORT
    agent = f"""#!/usr/bin/env python3
import json
import os
import sys
import shutil
import socket
import subprocess
import time
import urllib.request

VM_ID = {vm_id!r}
TOKEN = {token!r}
VERSION = "0.1.0"


def _warn(message):
    print(f"golem-metrics-agent: {{message}}", file=sys.stderr, flush=True)


def _default_gateway():
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        parts = out.strip().split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    except Exception as exc:
        _warn(f"failed to read default gateway: {{exc}}")
    return None


def _endpoint():
    override = os.environ.get("GOLEM_PROVIDER_METRICS_URL", "").strip()
    if override:
        return override.rstrip("/")
    host = os.environ.get("GOLEM_PROVIDER_HOST", "").strip() or _default_gateway()
    if not host:
        return ""
    return f"http://{{host}}:{port}/api/v1/monitoring/guest/{{VM_ID}}/samples"


def _read_cpu():
    def sample():
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            parts = [float(v) for v in fh.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        total = sum(parts)
        return idle, total

    idle1, total1 = sample()
    time.sleep(0.2)
    idle2, total2 = sample()
    total_delta = total2 - total1
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - ((idle2 - idle1) / total_delta))))


def _meminfo():
    data = {{}}
    with open("/proc/meminfo", "r", encoding="utf-8") as fh:
        for line in fh:
            key, raw = line.split(":", 1)
            data[key] = float(raw.strip().split()[0]) * 1024
    total = data.get("MemTotal")
    available = data.get("MemAvailable")
    used = total - available if total is not None and available is not None else None
    return used, total


def _disk():
    usage = shutil.disk_usage("/")
    return usage.used, usage.total


def _net():
    rx = 0
    tx = 0
    with open("/proc/net/dev", "r", encoding="utf-8") as fh:
        for line in fh.readlines()[2:]:
            iface, raw = line.split(":", 1)
            if iface.strip() == "lo":
                continue
            parts = raw.split()
            rx += int(parts[0])
            tx += int(parts[8])
    return rx, tx


def _load():
    try:
        return os.getloadavg()[0]
    except Exception as exc:
        _warn(f"failed to read load average: {{exc}}")
        return None


def collect():
    mem_used, mem_total = _meminfo()
    disk_used, disk_total = _disk()
    rx, tx = _net()
    return {{
        "token": TOKEN,
        "cpu_percent": _read_cpu(),
        "memory_used_bytes": mem_used,
        "memory_total_bytes": mem_total,
        "disk_used_bytes": disk_used,
        "disk_total_bytes": disk_total,
        "load_1m": _load(),
        "network_rx_bytes": rx,
        "network_tx_bytes": tx,
        "agent_version": VERSION,
    }}


def post(payload):
    url = _endpoint()
    if not url:
        raise RuntimeError("provider metrics endpoint unavailable")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={{"Content-Type": "application/json"}})
    urllib.request.urlopen(req, timeout=5).read()


while True:
    try:
        post(collect())
    except Exception as exc:
        _warn(f"failed to publish sample: {{exc}}")
    time.sleep(30)
"""
    service = """[Unit]
Description=Golem VM metrics agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/golem-metrics-agent
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
    return [
        {
            "path": "/usr/local/bin/golem-metrics-agent",
            "content": agent,
            "owner": "root:root",
            "permissions": "0755",
        },
        {
            "path": "/etc/systemd/system/golem-metrics-agent.service",
            "content": service,
            "owner": "root:root",
            "permissions": "0644",
        },
    ]


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
