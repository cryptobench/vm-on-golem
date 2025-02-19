# Provider Node Implementation Guide

## Overview

The Provider Node is responsible for:
1. Managing VM lifecycle using Multipass
2. Advertising available resources to the discovery service
3. Exposing a REST API for VM operations
4. Handling secure SSH key provisioning

## Implementation Details

### 1. VM Management Layer

```python
# src/provider/vm/multipass.py
from dataclasses import dataclass
import asyncio
import json
from typing import Optional

@dataclass
class VMConfig:
    name: str
    cpu: int
    memory: int
    storage: int
    image: str = "ubuntu:20.04"

class MultipassProvider:
    def __init__(self, multipass_path: str = "/usr/local/bin/multipass"):
        self.multipass_path = multipass_path

    async def create_vm(self, config: VMConfig) -> dict:
        """Create a new VM using Multipass."""
        cmd = [
            self.multipass_path, "launch",
            "--name", config.name,
            "--cpus", str(config.cpu),
            "--memory", f"{config.memory}GB",
            "--disk", f"{config.storage}GB",
            config.image
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise VMError(f"Failed to create VM: {stderr.decode()}")
            
        return {
            "name": config.name,
            "status": "running",
            "config": config.__dict__
        }

    async def provision_ssh_key(
        self,
        vm_name: str,
        key_path: str,
        username: str = "ubuntu"
    ) -> None:
        """Provision SSH key to VM."""
        # Transfer key file
        await asyncio.create_subprocess_exec(
            self.multipass_path, "transfer",
            key_path,
            f"{vm_name}:/home/{username}/.ssh/authorized_keys"
        )
```

### 2. Resource Advertisement

```python
# src/provider/discovery/advertiser.py
import aiohttp
import asyncio
from datetime import datetime
import psutil

class ResourceAdvertiser:
    def __init__(
        self,
        discovery_url: str,
        provider_id: str,
        update_interval: int = 240  # 4 minutes
    ):
        self.discovery_url = discovery_url
        self.provider_id = provider_id
        self.update_interval = update_interval
        self.session = aiohttp.ClientSession()

    async def start(self):
        """Start periodic resource advertisement."""
        while True:
            try:
                resources = await self.get_available_resources()
                await self.post_advertisement(resources)
            except Exception as e:
                logging.error(f"Failed to update advertisement: {e}")
            await asyncio.sleep(self.update_interval)

    async def get_available_resources(self) -> dict:
        """Get current available resources."""
        return {
            "cpu": psutil.cpu_count(),
            "memory": psutil.virtual_memory().available // (1024**3),  # GB
            "storage": psutil.disk_usage("/").free // (1024**3)  # GB
        }

    async def post_advertisement(self, resources: dict):
        """Post resource advertisement to discovery service."""
        async with self.session.post(
            f"{self.discovery_url}/api/v1/advertisements",
            headers={
                "X-Provider-ID": self.provider_id,
                "X-Provider-Signature": "signature"  # TODO: Implement signing
            },
            json={
                "ip_address": await self.get_public_ip(),
                "resources": resources,
                "country": "SE"  # TODO: Get from config
            }
        ) as response:
            if not response.ok:
                raise AdvertisementError(
                    f"Failed to post advertisement: {await response.text()}"
                )
```

### 3. REST API

```python
# src/provider/api/server.py
from fastapi import FastAPI, Depends, HTTPException
from typing import Optional

app = FastAPI()

class VMManager:
    def __init__(
        self,
        multipass: MultipassProvider,
        max_vms: int = 10
    ):
        self.multipass = multipass
        self.max_vms = max_vms
        self.active_vms = {}

    async def create_vm(self, config: VMConfig) -> dict:
        """Create a new VM if resources are available."""
        if len(self.active_vms) >= self.max_vms:
            raise VMError("Maximum VM limit reached")
            
        vm = await self.multipass.create_vm(config)
        self.active_vms[vm["name"]] = vm
        return vm

# API Routes
@app.post("/api/v1/vms")
async def create_vm(
    config: VMConfig,
    vm_manager: VMManager = Depends(get_vm_manager)
):
    """Create a new VM."""
    return await vm_manager.create_vm(config)

@app.post("/api/v1/vms/{vm_name}/ssh-keys")
async def add_ssh_key(
    vm_name: str,
    key: SSHKey,
    vm_manager: VMManager = Depends(get_vm_manager)
):
    """Add SSH key to VM."""
    if vm_name not in vm_manager.active_vms:
        raise HTTPException(status_code=404, detail="VM not found")
        
    await vm_manager.multipass.provision_ssh_key(
        vm_name,
        key.path
    )
    return {"status": "success"}
```

### 4. Configuration

```python
# src/provider/config.py
from pydantic import BaseSettings

class ProviderConfig(BaseSettings):
    provider_id: str
    discovery_url: str = "http://discovery.golem.network:7465"
    multipass_path: str = "/usr/bin/multipass"
    max_vms: int = 10
    update_interval: int = 240  # 4 minutes
    country: str = "SE"
    
    class Config:
        env_prefix = "GOLEM_PROVIDER_"
```

### 5. Main Application

```python
# src/provider/main.py
import asyncio
import logging
from contextlib import asynccontextmanager

class ProviderNode:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.multipass = MultipassProvider(config.multipass_path)
        self.vm_manager = VMManager(self.multipass, config.max_vms)
        self.advertiser = ResourceAdvertiser(
            config.discovery_url,
            config.provider_id,
            config.update_interval
        )

    async def start(self):
        """Start the provider node."""
        # Start resource advertisement
        asyncio.create_task(self.advertiser.start())
        
        # Start API server
        app = FastAPI()
        app.include_router(create_api_router(self.vm_manager))
        
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=7465
        )
        server = uvicorn.Server(config)
        await server.serve()

if __name__ == "__main__":
    config = ProviderConfig()
    provider = ProviderNode(config)
    asyncio.run(provider.start())
```

## Usage Example

1. Start the provider node:
```bash
export GOLEM_PROVIDER_ID="provider123"
python -m provider.main
```

2. The provider will automatically:
   - Start advertising resources every 4 minutes
   - Handle VM creation requests
   - Manage SSH key provisioning

## Error Handling

```python
# src/provider/errors.py
class ProviderError(Exception):
    """Base class for provider errors."""
    pass

class VMError(ProviderError):
    """VM operation error."""
    pass

class AdvertisementError(ProviderError):
    """Resource advertisement error."""
    pass
```

## Security Considerations

1. **Resource Validation**
   ```python
   def validate_resources(resources: dict) -> bool:
       """Validate resource availability before creating VM."""
       available = psutil.virtual_memory().available // (1024**3)
       if resources["memory"] > available:
           return False
       return True
   ```

2. **SSH Key Validation**
   ```python
   def validate_ssh_key(key: str) -> bool:
       """Validate SSH key format."""
       if not key.startswith("ssh-"):
           return False
       return True
   ```

This implementation focuses on the core responsibilities of a provider node:
1. Advertising resources to the discovery service
2. Managing VMs through Multipass
3. Handling basic VM operations via REST API

The provider maintains its advertisement by updating it every 4 minutes (allowing for a 1-minute buffer before the 5-minute expiration in the discovery service).
