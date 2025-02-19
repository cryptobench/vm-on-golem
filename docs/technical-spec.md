# VM on Golem - Technical Specification

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Component Specifications](#component-specifications)
4. [API Definitions](#api-definitions)
5. [Security Architecture](#security-architecture)
6. [Error Handling](#error-handling)
7. [Testing Strategy](#testing-strategy)
8. [Performance Considerations](#performance-considerations)

## System Overview

VM on Golem is a decentralized computing platform that enables users to rent and provide virtual machines (VMs) through a simple, user-friendly interface. The system is built around a central discovery service that acts as an advertisement board, where providers can post their available resources and requestors can find suitable providers.

### Core Principles
- Extreme Simplicity: One-command VM creation and management
- Direct Communication: Requestors talk directly to providers after discovery
- Minimal State: Discovery service only maintains current advertisements
- Self-Cleaning: Stale advertisements automatically expire after 5 minutes
- Provider Independence: Providers manage their own resources and VMs

### Key Features
- Simple CLI interface for VM management
- Secure SSH access to VMs
- Automatic provider discovery
- Direct provider-requestor communication
- Stateless discovery service

## Architecture

### High-Level Components

```
                                ┌─────────────────┐
                                │   Discovery     │
                                │    Service      │
                                │  (Ad Board)     │
                                └─────────────────┘
                                    ▲         ▲
                                    │         │
                            Query  │         │  Advertise
                                    │         │
                                    │         │
┌─────────────────┐                │         │                ┌─────────────────┐
│   Requestor     │                │         │                │    Provider     │
│     Node        │────────────────┘         └───────────────│     Node        │
└─────────────────┘                                          └─────────────────┘
        │                                                            ▲
        │                                                            │
        └────────────────────────────────────────────────────────────┘
                            Direct Communication
                          (After Provider Discovery)
```

### Component Roles

1. **Discovery Service**
   - Simple advertisement board
   - Providers post resource availability
   - Requestors query for matching providers
   - Advertisements expire after 5 minutes
   - No state beyond current advertisements

2. **Provider Node**
   - Manages local VMs using Multipass
   - Advertises available resources
   - Handles direct VM operations
   - Manages SSH access
   - Updates advertisement every 4 minutes

3. **Requestor Node**
   - Discovers providers through discovery service
   - Communicates directly with chosen provider
   - Manages VM lifecycle through provider's API
   - Tracks created VMs locally

### Database Requirements

All components in the VM on Golem project use SQLite as the database backend. This decision was made to:
- Simplify deployment and maintenance
- Reduce system dependencies
- Enable easy local development
- Provide portable data storage

SQLite databases are stored in the user's home directory under `.golem/<component-name>/` for each component.

### Component Details

#### 1. Provider Node
- **VM Management Layer (ExeUnit)**
  ```python
  class VMProvider:
      async def create_vm(self, config: VMConfig) -> VMInstance:
          """Create a new VM instance."""
          pass

      async def destroy_vm(self, id: str) -> None:
          """Destroy an existing VM."""
          pass

      async def provision_ssh_key(self, id: str, key: SSHKey) -> None:
          """Provision SSH key to VM."""
          pass

      async def get_vm_status(self, id: str) -> VMStatus:
          """Get current VM status."""
          pass

      async def scale_vm(self, id: str, new_config: VMConfig) -> None:
          """Scale VM resources."""
          pass
  ```

- **Resource Monitor**
  ```python
  class ResourceMonitor:
      async def get_cpu_usage(self) -> float:
          """Get current CPU usage percentage."""
          pass

      async def get_memory_usage(self) -> float:
          """Get current memory usage percentage."""
          pass

      async def get_disk_usage(self) -> float:
          """Get current disk usage percentage."""
          pass

      async def get_network_stats(self) -> NetworkStats:
          """Get current network statistics."""
          pass
  ```

- **Port Verification Tool**
  ```python
  class PortVerifier:
      async def check_port(self, port: int) -> bool:
          """Check if a specific port is available."""
          pass

      async def verify_required_ports(self) -> PortVerificationResult:
          """Verify all required ports are available."""
          pass
  ```

#### 2. Requestor Node
- **CLI Interface (using Click)**
  ```python
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
  def create(name: str, size: str):
      """Create a new VM"""
      pass

  @vm.command()
  @click.argument('name')
  def destroy(name: str):
      """Destroy a VM"""
      pass

  @vm.command()
  @click.argument('name')
  def start(name: str):
      """Start a VM"""
      pass

  @vm.command()
  @click.argument('name')
  def stop(name: str):
      """Stop a VM"""
      pass

  @vm.command()
  @click.argument('name')
  @click.option('--size', type=click.Choice(['small', 'medium', 'large']))
  def scale(name: str, size: str):
      """Scale VM resources"""
      pass

  @vm.command()
  @click.argument('name')
  def ssh(name: str):
      """SSH into a VM"""
      pass

  @vm.command()
  def list():
      """List all VMs"""
      pass
  ```

- **SSH Key Manager**
  ```python
  class SSHKeyManager:
      async def generate_key_pair(self) -> SSHKeyPair:
          """Generate new SSH key pair."""
          pass

      async def add_public_key(self, vm_id: str, key: str) -> None:
          """Add public key to VM."""
          pass

      async def remove_public_key(self, vm_id: str, key_id: str) -> None:
          """Remove public key from VM."""
          pass

      async def list_keys(self, vm_id: str) -> List[SSHKey]:
          """List all SSH keys for VM."""
          pass
  ```

#### 3. Discovery Service
- **Database Models (SQLAlchemy)**
  ```python
  from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
  from sqlalchemy.orm import declarative_base, relationship
  from sqlalchemy.sql import func

  Base = declarative_base()

  class Provider(Base):
      __tablename__ = "providers"

      id = Column(String, primary_key=True)
      ip_address = Column(String, nullable=False)
      country = Column(String(2), nullable=False)  # ISO 3166-1 alpha-2
      status = Column(String, nullable=False)
      last_seen = Column(DateTime, server_default=func.now())

      # Relationships
      resources = relationship("ProviderResources", back_populates="provider", uselist=False)
      pricing = relationship("ProviderPricing", back_populates="provider", uselist=False)

  class ProviderResources(Base):
      __tablename__ = "provider_resources"

      provider_id = Column(String, ForeignKey("providers.id"), primary_key=True)
      cpu = Column(Integer, nullable=False)
      memory = Column(Integer, nullable=False)
      storage = Column(Integer, nullable=False)
      updated_at = Column(DateTime, server_default=func.now())

      provider = relationship("Provider", back_populates="resources")

  class ProviderPricing(Base):
      __tablename__ = "provider_pricing"

      provider_id = Column(String, ForeignKey("providers.id"), primary_key=True)
      per_hour = Column(Float, nullable=False)
      currency = Column(String, nullable=False)
      updated_at = Column(DateTime, server_default=func.now())

      provider = relationship("Provider", back_populates="pricing")
  ```

- **Repository Pattern**
  ```python
  class ProviderRepository:
      def __init__(self, session: AsyncSession):
          self.session = session

      async def create(self, registration: ProviderRegistration) -> Provider:
          """Register a new provider."""
          provider = Provider(
              id=str(uuid.uuid4()),
              ip_address=registration.ip_address,
              country=registration.country,
              status='active'
          )
          self.session.add(provider)
          await self.session.commit()
          return provider

      async def find_by_requirements(
          self, 
          requirements: ResourceRequirements
      ) -> List[Provider]:
          """Find providers matching requirements."""
          query = select(Provider).join(ProviderResources).where(
              Provider.status == 'active',
              ProviderResources.cpu >= requirements.cpu,
              ProviderResources.memory >= requirements.memory,
              ProviderResources.storage >= requirements.storage
          )
          result = await self.session.execute(query)
          return result.scalars().all()
  ```

## API Definitions

### Data Models (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class VMConfig(BaseModel):
    name: str = Field(..., pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    size: Optional[str] = Field(None, enum=['small', 'medium', 'large'])
    cpu: Optional[int] = Field(None, ge=1)
    memory: Optional[int] = Field(None, ge=1)
    storage: Optional[int] = Field(None, ge=10)

class SSHKey(BaseModel):
    key: str
    name: str
    fingerprint: str

class VMStatus(BaseModel):
    id: UUID
    name: str
    status: str
    ip_address: Optional[str]
    ssh_port: Optional[int]
    created_at: datetime
    updated_at: datetime

class ResourceRequirements(BaseModel):
    cpu: int = Field(..., ge=1)
    memory: int = Field(..., ge=1)
    storage: int = Field(..., ge=10)
```

### Provider API (FastAPI)

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI(title="VM Provider API")

# Dependency for database session
async def get_db():
    async with AsyncSession() as session:
        yield session

# VM Management
@app.post("/api/v1/vms", response_model=VMStatus)
async def create_vm(
    config: VMConfig,
    db: AsyncSession = Depends(get_db),
    auth: AuthInfo = Depends(verify_signature)
):
    """Create a new VM instance."""
    try:
        vm = await vm_provider.create_vm(config)
        return vm
    except ResourceError as e:
        raise HTTPException(status_code=507, detail=str(e))

@app.delete("/api/v1/vms/{vm_id}")
async def destroy_vm(
    vm_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthInfo = Depends(verify_signature)
):
    """Destroy an existing VM."""
    await vm_provider.destroy_vm(vm_id)
    return {"status": "success"}

@app.get("/api/v1/vms/{vm_id}", response_model=VMStatus)
async def get_vm_status(
    vm_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthInfo = Depends(verify_signature)
):
    """Get VM status."""
    return await vm_provider.get_vm_status(vm_id)

# SSH Key Management
@app.post("/api/v1/ssh-keys")
async def add_ssh_key(
    key: SSHKey,
    vm_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthInfo = Depends(verify_signature)
):
    """Add SSH key to VM."""
    await ssh_manager.add_public_key(vm_id, key)
    return {"status": "success"}
```

### Discovery Service API (FastAPI)

```python
from fastapi import FastAPI, Depends, Query
from typing import List

app = FastAPI(title="VM Discovery Service")

# Provider Management
@app.post("/api/v1/providers", response_model=ProviderResponse)
async def register_provider(
    registration: ProviderRegistration,
    db: AsyncSession = Depends(get_db),
    auth: AuthInfo = Depends(verify_signature)
):
    """Register a new provider."""
    provider = await provider_repo.create(registration)
    return provider

@app.get("/api/v1/providers", response_model=List[Provider])
async def list_providers(
    cpu: Optional[int] = Query(None, ge=1),
    memory: Optional[int] = Query(None, ge=1),
    storage: Optional[int] = Query(None, ge=10),
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db)
):
    """List available providers matching criteria."""
    requirements = ResourceRequirements(
        cpu=cpu or 1,
        memory=memory or 1,
        storage=storage or 10
    )
    return await provider_repo.find_by_requirements(requirements)

@app.get("/api/v1/resources")
async def query_resources(
    requirements: ResourceRequirements,
    db: AsyncSession = Depends(get_db)
):
    """Query available resources across providers."""
    providers = await provider_repo.find_by_requirements(requirements)
    return {
        "available": [
            {
                "provider_id": p.id,
                "resources": p.resources,
                "pricing": p.pricing
            }
            for p in providers
        ]
    }
```

## Security Architecture

### Authentication Flow

1. Node Identity
```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from dataclasses import dataclass
from datetime import datetime
import jwt

@dataclass
class NodeIdentity:
    public_key: str
    private_key: str
    node_id: str
    created_at: datetime

class IdentityManager:
    def __init__(self, key_path: str):
        self.key_path = key_path

    async def generate_identity(self) -> NodeIdentity:
        """Generate new node identity."""
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096
        )
        public_key = private_key.public_key()
        
        # Generate node ID from public key
        node_id = self.generate_node_id(public_key)
        
        # Save keys securely
        await self.save_keys(private_key, public_key, node_id)
        
        return NodeIdentity(
            public_key=public_key.public_bytes(...),
            private_key=private_key.private_bytes(...),
            node_id=node_id,
            created_at=datetime.utcnow()
        )

    def generate_node_id(self, public_key) -> str:
        """Generate unique node ID from public key."""
        digest = hashes.Hash(hashes.SHA256())
        digest.update(public_key.public_bytes(...))
        return digest.finalize().hex()
```

2. Request Signing
```python
from cryptography.hazmat.primitives import serialization
from typing import Any, Dict

class RequestSigner:
    def __init__(self, identity: NodeIdentity):
        self.identity = identity
        self.private_key = serialization.load_pem_private_key(
            identity.private_key.encode(),
            password=None
        )

    async def sign_request(
        self,
        method: str,
        path: str,
        body: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """Sign an API request."""
        timestamp = datetime.utcnow().isoformat()
        message = f"{timestamp}{method}{path}"
        if body:
            message += json.dumps(body, sort_keys=True)

        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return {
            "X-Golem-Node-ID": self.identity.node_id,
            "X-Golem-Timestamp": timestamp,
            "X-Golem-Signature": base64.b64encode(signature).decode()
        }

    def generate_jwt(self, claims: Dict[str, Any]) -> str:
        """Generate JWT token for session authentication."""
        return jwt.encode(
            {
                **claims,
                "iss": self.identity.node_id,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            self.identity.private_key,
            algorithm="RS256"
        )
```

3. SSH Access
```python
from cryptography.hazmat.primitives import asymmetric
import asyncssh
from pathlib import Path

class SSHManager:
    def __init__(self, keys_dir: Path):
        self.keys_dir = keys_dir

    async def generate_key_pair(self, name: str) -> SSHKeyPair:
        """Generate new SSH key pair for VM access."""
        # Generate ED25519 key pair
        private_key = asyncssh.generate_private_key('ssh-ed25519')
        
        # Save keys
        key_path = self.keys_dir / name
        key_path.mkdir(parents=True, exist_ok=True)
        
        private_key_path = key_path / 'id_ed25519'
        public_key_path = key_path / 'id_ed25519.pub'
        
        private_key.write_private_key(str(private_key_path))
        private_key.write_public_key(str(public_key_path))
        
        # Set correct permissions
        private_key_path.chmod(0o600)
        public_key_path.chmod(0o644)
        
        return SSHKeyPair(
            private_key=str(private_key_path),
            public_key=str(public_key_path),
            fingerprint=private_key.get_fingerprint()
        )

    async def provision_key(
        self,
        vm_id: str,
        key: SSHKeyPair,
        username: str = "ubuntu"
    ) -> None:
        """Provision SSH key to VM."""
        async with asyncssh.connect(
            host=vm.ip_address,
            port=vm.ssh_port,
            username=username,
            client_keys=[key.private_key],
            known_hosts=None  # First connection
        ) as conn:
            await conn.run(f'mkdir -p ~/.ssh')
            await conn.run(f'chmod 700 ~/.ssh')
            await conn.sftp().put(
                key.public_key,
                '.ssh/authorized_keys'
            )
            await conn.run('chmod 600 ~/.ssh/authorized_keys')
```

### Security Measures
- Asymmetric encryption for node authentication
- JWT tokens for API authentication
- Secure SSH key provisioning
- Network isolation between VMs
- Resource usage limits
- Regular security audits

## Error Handling

### Error Handling System

```python
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class ErrorCode(str, Enum):
    # Authentication Errors
    AUTH_INVALID_TOKEN = "AUTH_001"
    AUTH_EXPIRED_TOKEN = "AUTH_002"
    AUTH_MISSING_SIGNATURE = "AUTH_003"
    
    # Resource Errors
    RESOURCE_NOT_FOUND = "RES_001"
    RESOURCE_EXHAUSTED = "RES_002"
    RESOURCE_UNAVAILABLE = "RES_003"
    
    # VM Errors
    VM_CREATE_FAILED = "VM_001"
    VM_NOT_FOUND = "VM_002"
    VM_ALREADY_EXISTS = "VM_003"
    
    # Network Errors
    NETWORK_TIMEOUT = "NET_001"
    NETWORK_UNREACHABLE = "NET_002"
    NETWORK_PORT_BLOCKED = "NET_003"

class GolemError(Exception):
    """Base exception for all Golem errors."""
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.details = details
        self.timestamp = datetime.utcnow()
        super().__init__(message)

class AuthError(GolemError):
    """Authentication and authorization errors."""
    pass

class ResourceError(GolemError):
    """Resource allocation and management errors."""
    pass

class VMError(GolemError):
    """VM operation errors."""
    pass

class NetworkError(GolemError):
    """Network-related errors."""
    pass

# Error response model
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]]
    timestamp: datetime
    request_id: Optional[str]

# FastAPI error handler
@app.exception_handler(GolemError)
async def golem_error_handler(request: Request, error: GolemError):
    return JSONResponse(
        status_code=error_status_codes.get(error.code, 500),
        content=ErrorResponse(
            code=error.code,
            message=error.message,
            details=error.details,
            timestamp=error.timestamp,
            request_id=request.state.request_id
        ).dict()
    )

# Example usage
async def create_vm(config: VMConfig) -> VMInstance:
    try:
        # Attempt to create VM
        if not await check_resources(config):
            raise ResourceError(
                code=ErrorCode.RESOURCE_EXHAUSTED,
                message="Insufficient resources to create VM",
                details={
                    "requested": config.dict(),
                    "available": await get_available_resources()
                }
            )
            
        # Create VM implementation...
        
    except MultipassError as e:
        raise VMError(
            code=ErrorCode.VM_CREATE_FAILED,
            message="Failed to create VM using Multipass",
            details={"multipass_error": str(e)}
        )
    except NetworkError as e:
        raise NetworkError(
            code=ErrorCode.NETWORK_UNREACHABLE,
            message="Network connectivity issues",
            details={"original_error": str(e)}
        )
```

### Error Recovery Strategies

```python
class ErrorRecoveryManager:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    async def handle_error(
        self,
        error: GolemError,
        context: Dict[str, Any]
    ) -> None:
        """Handle errors with appropriate recovery strategies."""
        if isinstance(error, ResourceError):
            await self.handle_resource_error(error, context)
        elif isinstance(error, VMError):
            await self.handle_vm_error(error, context)
        elif isinstance(error, NetworkError):
            await self.handle_network_error(error, context)
        else:
            raise error  # Unhandled error type

    async def handle_resource_error(
        self,
        error: ResourceError,
        context: Dict[str, Any]
    ) -> None:
        """Handle resource-related errors."""
        if error.code == ErrorCode.RESOURCE_EXHAUSTED:
            # Try to free up resources
            await self.cleanup_unused_resources()
            # Retry with reduced requirements
            if context.get("can_reduce_requirements"):
                await self.retry_with_reduced_requirements(context)
        elif error.code == ErrorCode.RESOURCE_UNAVAILABLE:
            # Wait and retry
            await self.retry_with_backoff(context)

    async def handle_vm_error(
        self,
        error: VMError,
        context: Dict[str, Any]
    ) -> None:
        """Handle VM-related errors."""
        if error.code == ErrorCode.VM_CREATE_FAILED:
            # Cleanup any partial resources
            await self.cleanup_failed_vm(context)
            # Try alternative provider
            await self.try_alternative_provider(context)

    async def retry_with_backoff(
        self,
        context: Dict[str, Any],
        base_delay: float = 1.0,
        max_delay: float = 30.0
    ) -> None:
        """Implement exponential backoff for retries."""
        for attempt in range(self.max_retries):
            delay = min(base_delay * (2 ** attempt), max_delay)
            await asyncio.sleep(delay)
            try:
                await self.retry_operation(context)
                return  # Success
            except GolemError as e:
                if attempt == self.max_retries - 1:
                    raise  # Last attempt failed
```

## Testing Strategy

### Unit Testing (pytest)

```python
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

class TestVMProvider:
    @pytest.fixture
    async def provider(self):
        return VMProvider(
            multipass_path="/usr/bin/multipass",
            max_vms=10
        )

    @pytest.mark.asyncio
    async def test_create_vm(self, provider):
        """Test VM creation with valid config."""
        config = VMConfig(
            name="test-vm",
            size="small",
            cpu=1,
            memory=1,
            storage=20
        )
        
        with patch('multipass.MultipassClient') as mock_client:
            mock_client.launch = AsyncMock()
            vm = await provider.create_vm(config)
            
            assert vm.name == "test-vm"
            assert vm.status == "running"
            mock_client.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_vm_resource_error(self, provider):
        """Test VM creation with insufficient resources."""
        config = VMConfig(
            name="test-vm",
            size="xlarge",
            cpu=32,
            memory=128,
            storage=1000
        )
        
        with pytest.raises(ResourceError) as exc_info:
            await provider.create_vm(config)
            
        assert exc_info.value.code == ErrorCode.RESOURCE_EXHAUSTED

class TestSSHManager:
    @pytest.fixture
    def ssh_manager(self, tmp_path):
        return SSHManager(keys_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_generate_key_pair(self, ssh_manager):
        """Test SSH key pair generation."""
        key_pair = await ssh_manager.generate_key_pair("test-vm")
        
        assert key_pair.private_key.exists()
        assert key_pair.public_key.exists()
        assert key_pair.private_key.stat().st_mode & 0o777 == 0o600
        assert key_pair.public_key.stat().st_mode & 0o777 == 0o644
```

### Integration Testing (pytest)

```python
class TestProviderAPI:
    @pytest.fixture
    async def client(self):
        app = FastAPI()
        app.include_router(provider_router)
        
        async with AsyncClient(app=app) as client:
            yield client

    @pytest.mark.asyncio
    async def test_create_vm_flow(self, client):
        """Test complete VM creation flow."""
        # 1. Create VM
        response = await client.post(
            "/api/v1/vms",
            json={
                "name": "test-vm",
                "size": "small"
            },
            headers=await generate_auth_headers()
        )
        assert response.status_code == 201
        vm_id = response.json()["id"]
        
        # 2. Add SSH key
        key_response = await client.post(
            f"/api/v1/vms/{vm_id}/ssh-keys",
            json={
                "key": "ssh-rsa AAAA...",
                "name": "test-key"
            }
        )
        assert key_response.status_code == 200
        
        # 3. Verify VM status
        status_response = await client.get(f"/api/v1/vms/{vm_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "running"
```

### End-to-End Testing (pytest-asyncio)

```python
@pytest.mark.asyncio
class TestVMLifecycle:
    async def test_complete_vm_lifecycle(self):
        """Test complete VM lifecycle from creation to destruction."""
        # 1. Initialize components
        provider = VMProvider()
        discovery = DiscoveryService()
        requestor = RequestorNode()
        
        # 2. Create VM
        vm = await requestor.create_vm(
            name="test-vm",
            size="small"
        )
        
        try:
            # 3. Verify VM is running
            assert await vm.wait_for_status("running")
            
            # 4. Test SSH access
            async with vm.ssh_connect() as conn:
                result = await conn.run('echo "test"')
                assert result.exit_status == 0
            
            # 5. Test scaling
            await vm.scale(size="medium")
            await vm.wait_for_status("running")
            
            # 6. Verify new resources
            status = await vm.get_status()
            assert status.resources.cpu == 2
            assert status.resources.memory == 4
            
        finally:
            # Cleanup
            await vm.destroy()
            
        # Verify cleanup
        with pytest.raises(VMError):
            await vm.get_status()
```

### Performance Testing (locust)

```python
from locust import HttpUser, task, between

class VMUser(HttpUser):
    wait_time = between(1, 2)
    
    def on_start(self):
        """Setup authentication."""
        self.auth_headers = self.generate_auth_headers()
    
    @task(3)
    def create_vm(self):
        """Test VM creation performance."""
        self.client.post(
            "/api/v1/vms",
            json={
                "name": f"test-vm-{self.user_id}",
                "size": "small"
            },
            headers=self.auth_headers
        )
    
    @task(1)
    def list_vms(self):
        """Test VM listing performance."""
        self.client.get("/api/v1/vms", headers=self.auth_headers)

class ProviderUser(HttpUser):
    wait_time = between(5, 10)
    
    @task
    def update_resources(self):
        """Test resource update performance."""
        self.client.post(
            "/api/v1/resources",
            json={
                "cpu": 80,
                "memory": 70,
                "storage": 60
            },
            headers=self.auth_headers
        )
```

### Test Configuration

```python
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
markers =
    asyncio: mark test as async
    integration: mark test as integration test
    e2e: mark test as end-to-end test
    performance: mark test as performance test

# conftest.py
import pytest
import asyncio
from pathlib import Path

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db():
    """Setup test database."""
    db_path = Path("test.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()
    db_path.unlink()
```

### Continuous Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest tests/unit
        pytest tests/integration
        pytest tests/e2e
    
    - name: Run performance tests
      run: |
        locust --headless -f tests/performance/locustfile.py
```

## Performance Considerations

### Optimization Strategies

#### 1. Resource Allocation
```python
from functools import lru_cache
from typing import Dict, List
import asyncio

class ResourceOptimizer:
    def __init__(self):
        self.resource_cache = {}
        self.lock = asyncio.Lock()

    @lru_cache(maxsize=1000)
    async def get_optimal_provider(
        self,
        requirements: ResourceRequirements
    ) -> Provider:
        """Get optimal provider for given requirements (cached)."""
        providers = await self.get_available_providers(requirements)
        return self.rank_providers(providers)[0]

    async def preload_resources(self) -> None:
        """Preload resource information for faster allocation."""
        async with self.lock:
            providers = await self.provider_repo.get_all_active()
            self.resource_cache = {
                p.id: await self.get_provider_resources(p.id)
                for p in providers
            }

    def estimate_vm_creation_time(
        self,
        config: VMConfig,
        provider: Provider
    ) -> float:
        """Estimate VM creation time based on historical data."""
        return self.creation_time_model.predict({
            'cpu': config.cpu,
            'memory': config.memory,
            'storage': config.storage,
            'provider_load': provider.current_load
        })
```

#### 2. Network Optimization
```python
import aiohttp
from asyncio import Queue
from typing import Dict, Any

class NetworkOptimizer:
    def __init__(self):
        self.session_pool = aiohttp.ClientSession()
        self.request_queue: Queue[Dict[str, Any]] = Queue()
        self.batch_size = 10
        self.batch_timeout = 0.1

    async def batch_requests(self) -> None:
        """Batch multiple requests together."""
        while True:
            batch = []
            try:
                while len(batch) < self.batch_size:
                    request = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=self.batch_timeout
                    )
                    batch.append(request)
            except asyncio.TimeoutError:
                if batch:
                    await self.process_batch(batch)

    async def process_batch(
        self,
        requests: List[Dict[str, Any]]
    ) -> None:
        """Process a batch of requests efficiently."""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.make_request(session, req)
                for req in requests
            ]
            await asyncio.gather(*tasks)
```

#### 3. Caching System
```python
from redis import asyncio as aioredis
from typing import Optional, Any
import pickle

class CacheManager:
    def __init__(self):
        self.redis = aioredis.Redis()
        self.local_cache = {}
        self.ttl = 300  # 5 minutes

    async def get_cached(
        self,
        key: str,
        fetch_func: callable
    ) -> Any:
        """Get data with two-level caching."""
        # Try local cache first
        if key in self.local_cache:
            return self.local_cache[key]

        # Try Redis cache
        cached = await self.redis.get(key)
        if cached:
            value = pickle.loads(cached)
            self.local_cache[key] = value
            return value

        # Fetch fresh data
        value = await fetch_func()
        
        # Update both caches
        await self.redis.setex(
            key,
            self.ttl,
            pickle.dumps(value)
        )
        self.local_cache[key] = value
        
        return value

    async def invalidate(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
            for key in self.local_cache.keys():
                if any(k.decode() in key for k in keys):
                    del self.local_cache[key]
```

### Monitoring and Metrics

#### 1. Prometheus Integration
```python
from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

# Metrics
VM_CREATION_TIME = Histogram(
    'vm_creation_seconds',
    'Time spent creating VMs',
    ['size', 'provider']
)
ACTIVE_VMS = Gauge(
    'active_vms_total',
    'Number of active VMs',
    ['provider']
)
ERROR_COUNTER = Counter(
    'errors_total',
    'Total number of errors',
    ['type', 'code']
)

# Decorators for automatic metric collection
def track_vm_creation(size: str, provider: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                VM_CREATION_TIME.labels(
                    size=size,
                    provider=provider
                ).observe(time.time() - start)
                ACTIVE_VMS.labels(provider=provider).inc()
                return result
            except Exception as e:
                ERROR_COUNTER.labels(
                    type='vm_creation',
                    code=getattr(e, 'code', 'unknown')
                ).inc()
                raise
        return wrapper
    return decorator
```

#### 2. Performance Monitoring
```python
from datadog import initialize, statsd
import resource
import psutil

class PerformanceMonitor:
    def __init__(self):
        self.process = psutil.Process()
        initialize(statsd_host='localhost', statsd_port=8125)

    async def collect_metrics(self):
        """Collect and report system metrics."""
        while True:
            # System metrics
            cpu_percent = psutil.cpu_percent()
            memory_info = psutil.virtual_memory()
            
            # Process metrics
            process_memory = self.process.memory_info().rss
            process_cpu = self.process.cpu_percent()
            
            # Report metrics
            statsd.gauge('system.cpu.usage', cpu_percent)
            statsd.gauge('system.memory.used', memory_info.used)
            statsd.gauge('process.memory.rss', process_memory)
            statsd.gauge('process.cpu.usage', process_cpu)
            
            await asyncio.sleep(10)

    @contextmanager
    def track_operation(self, name: str):
        """Track operation timing and resource usage."""
        start_time = time.time()
        start_resources = resource.getrusage(resource.RUSAGE_SELF)
        
        try:
            yield
        finally:
            end_time = time.time()
            end_resources = resource.getrusage(resource.RUSAGE_SELF)
            
            duration = end_time - start_time
            cpu_time = (
                end_resources.ru_utime - start_resources.ru_utime +
                end_resources.ru_stime - start_resources.ru_stime
            )
            
            statsd.timing(f'operation.{name}.duration', duration * 1000)
            statsd.gauge(f'operation.{name}.cpu_time', cpu_time)
```

#### 3. Alerting System
```python
from typing import Callable
import asyncio
import logging

class AlertManager:
    def __init__(self):
        self.alert_handlers: Dict[str, List[Callable]] = {}
        self.thresholds = {
            'vm_creation_time': 60,  # seconds
            'error_rate': 0.1,       # 10%
            'resource_usage': 0.9    # 90%
        }

    async def monitor_metrics(self):
        """Monitor metrics and trigger alerts."""
        while True:
            # Check VM creation time
            creation_time = VM_CREATION_TIME.observe()
            if creation_time > self.thresholds['vm_creation_time']:
                await self.trigger_alert(
                    'high_creation_time',
                    f'VM creation taking {creation_time}s'
                )

            # Check error rate
            error_rate = ERROR_COUNTER.rate()
            if error_rate > self.thresholds['error_rate']:
                await self.trigger_alert(
                    'high_error_rate',
                    f'Error rate at {error_rate*100}%'
                )

            # Check resource usage
            for provider in ACTIVE_VMS.providers:
                usage = await self.get_provider_usage(provider)
                if usage > self.thresholds['resource_usage']:
                    await self.trigger_alert(
                        'high_resource_usage',
                        f'Provider {provider} at {usage*100}% capacity'
                    )

            await asyncio.sleep(60)

    async def trigger_alert(
        self,
        alert_type: str,
        message: str
    ) -> None:
        """Trigger alerts for registered handlers."""
        handlers = self.alert_handlers.get(alert_type, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logging.error(
                    f"Alert handler failed: {e}",
                    exc_info=True
                )
```

These optimizations and monitoring systems ensure:
1. Efficient resource utilization through smart caching and allocation
2. Minimal network overhead with request batching
3. Comprehensive performance monitoring
4. Early detection of performance issues
5. Automated alerting for system health

The implementation uses modern Python async features and industry-standard monitoring tools to provide optimal performance and observability.

This document will be continuously updated as the project evolves and new requirements are identified.
