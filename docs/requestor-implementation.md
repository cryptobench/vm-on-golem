# Requestor Node Implementation Guide

## Overview

The Requestor Node is responsible for:

1. Discovering available providers through the discovery service
2. Creating and managing VMs on chosen providers
3. Providing a simple CLI interface for VM operations
4. Managing SSH access to VMs

## Implementation Details

### 1. Provider Discovery

```python
# src/requestor/discovery/client.py
import aiohttp
from typing import List, Optional
from datetime import datetime

class DiscoveryClient:
    def __init__(self, discovery_url: str):
        self.discovery_url = discovery_url
        self.session = aiohttp.ClientSession()

    async def find_providers(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None
    ) -> List[dict]:
        """Find providers matching requirements."""
        params = {
            k: v for k, v in {
                'cpu': cpu,
                'memory': memory,
                'storage': storage,
                'country': country
            }.items() if v is not None
        }

        async with self.session.get(
            f"{self.discovery_url}/api/v1/advertisements",
            params=params
        ) as response:
            if not response.ok:
                raise DiscoveryError(
                    f"Failed to find providers: {await response.text()}"
                )
            return await response.json()
```

### 2. Provider Communication

```python
# src/requestor/provider/client.py
import aiohttp
from typing import Optional
import asyncssh

class ProviderClient:
    def __init__(self, provider_url: str):
        self.provider_url = provider_url
        self.session = aiohttp.ClientSession()

    async def create_vm(
        self,
        name: str,
        cpu: int,
        memory: int,
        storage: int
    ) -> dict:
        """Create a VM on the provider."""
        async with self.session.post(
            f"{self.provider_url}/api/v1/vms",
            json={
                "name": name,
                "cpu": cpu,
                "memory": memory,
                "storage": storage
            }
        ) as response:
            if not response.ok:
                raise ProviderError(
                    f"Failed to create VM: {await response.text()}"
                )
            return await response.json()

    async def add_ssh_key(
        self,
        vm_name: str,
        key_path: str
    ) -> None:
        """Add SSH key to VM."""
        with open(key_path, 'r') as f:
            key_content = f.read()

        async with self.session.post(
            f"{self.provider_url}/api/v1/vms/{vm_name}/ssh-keys",
            json={
                "key": key_content,
                "name": "default"
            }
        ) as response:
            if not response.ok:
                raise ProviderError(
                    f"Failed to add SSH key: {await response.text()}"
                )
```

### 3. CLI Interface

```python
# src/requestor/cli/main.py
import click
import asyncio
from typing import Optional

@click.group()
def cli():
    """VM on Golem management CLI"""
    pass

@cli.group()
def vm():
    """VM management commands"""
    pass

@vm.command()
@click.argument('name')
@click.option('--size', type=click.Choice(['small', 'medium', 'large']))
@click.option('--country', help='Preferred provider country')
async def create(name: str, size: str, country: Optional[str] = None):
    """Create a new VM."""
    # Size to resource mapping
    sizes = {
        'small': {'cpu': 1, 'memory': 1, 'storage': 10},
        'medium': {'cpu': 2, 'memory': 4, 'storage': 20},
        'large': {'cpu': 4, 'memory': 8, 'storage': 40}
    }
    resources = sizes[size]

    # Find provider
    discovery = DiscoveryClient(config.discovery_url)
    providers = await discovery.find_providers(
        cpu=resources['cpu'],
        memory=resources['memory'],
        storage=resources['storage'],
        country=country
    )

    if not providers:
        click.echo("No suitable providers found")
        return

    # Use first available provider
    provider = providers[0]
    client = ProviderClient(f"http://{provider['ip_address']}:9001")

    # Create VM
    vm = await client.create_vm(
        name=name,
        **resources
    )

    # Add SSH key
    key_path = config.ssh_key_path
    await client.add_ssh_key(name, key_path)

    click.echo(f"""
✅ VM '{name}' created successfully!
-------------------------------------------------------------
SSH Access       : ssh ubuntu@{provider['ip_address']}
IP Address      : {provider['ip_address']}
Port            : 22
VM Status       : running
Allocated Size  : {size}
-------------------------------------------------------------
Note: Remember to change your SSH password upon first login.
    """)

@vm.command()
@click.argument('name')
async def ssh(name: str):
    """SSH into a VM."""
    # Find VM in local database
    vm = await db.get_vm(name)
    if not vm:
        click.echo(f"VM '{name}' not found")
        return

    # Execute SSH command
    cmd = [
        "ssh",
        "-i", config.ssh_key_path,
        f"ubuntu@{vm['ip_address']}"
    ]
    await asyncio.create_subprocess_exec(*cmd)
```

### 4. Configuration

```python
# src/requestor/config.py
from pydantic import BaseSettings
from pathlib import Path

class RequestorConfig(BaseSettings):
    discovery_url: str = "http://discovery.golem.network:9001"
    ssh_key_path: Path = Path.home() / ".ssh" / "golem_key"

    class Config:
        env_prefix = "GOLEM_REQUESTOR_"
```

### 5. Local State Management

```python
# src/requestor/db/sqlite.py
import aiosqlite
from typing import Optional, Dict
import json

class Database:
    def __init__(self, db_path: str = "~/.golem/vms.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        """Initialize database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vms (
                    name TEXT PRIMARY KEY,
                    provider_ip TEXT NOT NULL,
                    config TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def save_vm(self, name: str, provider_ip: str, config: dict):
        """Save VM details."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO vms (name, provider_ip, config) VALUES (?, ?, ?)",
                (name, provider_ip, json.dumps(config))
            )
            await db.commit()

    async def get_vm(self, name: str) -> Optional[Dict]:
        """Get VM details."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM vms WHERE name = ?",
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "name": row[0],
                        "ip_address": row[1],
                        "config": json.loads(row[2]),
                        "created_at": row[3]
                    }
                return None
```

## Usage Example

1. Create a new VM:

```bash
golem vm create my-webserver --size medium --country SE
```

2. SSH into the VM:

```bash
golem vm ssh my-webserver
```

## Error Handling

```python
# src/requestor/errors.py
class RequestorError(Exception):
    """Base class for requestor errors."""
    pass

class DiscoveryError(RequestorError):
    """Discovery service error."""
    pass

class ProviderError(RequestorError):
    """Provider communication error."""
    pass
```

This implementation focuses on:

1. Simple provider discovery through the discovery service
2. Direct communication with providers
3. Easy-to-use CLI interface
4. Local state management for VM tracking

The requestor node maintains minimal state, primarily using the discovery service to find providers and then communicating directly with them for VM operations.
