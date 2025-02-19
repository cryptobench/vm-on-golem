# VM on Golem Security Guide

## Overview

This document outlines the security measures implemented in VM on Golem, focusing on:
1. Provider authentication for advertisements
2. SSH key management for VM access
3. Network security considerations
4. Resource isolation

## Provider Authentication

### 1. Advertisement Signing

Providers must sign their advertisements to prevent impersonation:

```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

class ProviderSigner:
    def __init__(self, private_key_path: str):
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )

    def sign_advertisement(self, advertisement: dict) -> str:
        """Sign provider advertisement."""
        # Create message from advertisement data
        message = f"{advertisement['ip_address']}{json.dumps(advertisement['resources'])}"
        
        # Sign message
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode()
```

### 2. Signature Verification

The discovery service verifies advertisement signatures:

```python
class SignatureVerifier:
    def verify_signature(
        self,
        provider_id: str,
        advertisement: dict,
        signature: str
    ) -> bool:
        """Verify advertisement signature."""
        # Get provider's public key
        public_key = self.get_provider_public_key(provider_id)
        
        # Recreate message
        message = f"{advertisement['ip_address']}{json.dumps(advertisement['resources'])}"
        
        try:
            # Verify signature
            public_key.verify(
                base64.b64decode(signature),
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False
```

## SSH Key Management

### 1. Key Generation

Secure SSH key generation for VM access:

```python
import asyncssh
from pathlib import Path

class SSHKeyManager:
    def __init__(self, keys_dir: Path):
        self.keys_dir = keys_dir
        self.keys_dir.mkdir(parents=True, exist_ok=True)

    async def generate_key_pair(self, name: str) -> SSHKeyPair:
        """Generate new SSH key pair."""
        # Use ED25519 for better security
        private_key = asyncssh.generate_private_key('ssh-ed25519')
        
        # Save keys with proper permissions
        key_path = self.keys_dir / name
        key_path.mkdir(exist_ok=True)
        
        private_key_path = key_path / 'id_ed25519'
        public_key_path = key_path / 'id_ed25519.pub'
        
        private_key.write_private_key(str(private_key_path))
        private_key.write_public_key(str(public_key_path))
        
        # Set restrictive permissions
        private_key_path.chmod(0o600)
        public_key_path.chmod(0o644)
        
        return SSHKeyPair(
            private_key=str(private_key_path),
            public_key=str(public_key_path),
            fingerprint=private_key.get_fingerprint()
        )
```

### 2. Key Provisioning

Secure key provisioning to VMs:

```python
class VMKeyProvisioner:
    async def provision_key(
        self,
        vm_id: str,
        key: SSHKeyPair,
        username: str = "ubuntu"
    ) -> None:
        """Provision SSH key to VM."""
        # Connect without storing host key (first connection)
        async with asyncssh.connect(
            host=vm.ip_address,
            port=vm.ssh_port,
            username=username,
            client_keys=[key.private_key],
            known_hosts=None
        ) as conn:
            # Create .ssh directory with proper permissions
            await conn.run('mkdir -p ~/.ssh')
            await conn.run('chmod 700 ~/.ssh')
            
            # Add public key
            await conn.sftp().put(
                key.public_key,
                '.ssh/authorized_keys'
            )
            
            # Set proper permissions
            await conn.run('chmod 600 ~/.ssh/authorized_keys')
```

## Network Security

### 1. Port Verification

Providers must verify required ports are open:

```python
import socket
import asyncio

class PortVerifier:
    REQUIRED_PORTS = [22, 80, 443, 7465]  # SSH, HTTP, HTTPS, Golem

    async def verify_ports(self) -> dict:
        """Verify all required ports are open."""
        results = {}
        for port in self.REQUIRED_PORTS:
            results[port] = await self.check_port(port)
        return results

    async def check_port(self, port: int) -> bool:
        """Check if a port is open."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('0.0.0.0', port))
            return result == 0
        finally:
            sock.close()
```

### 2. Network Isolation

VMs must be properly isolated:

```python
class NetworkIsolation:
    def setup_network_isolation(self, vm_name: str) -> None:
        """Setup network isolation for VM."""
        # Create isolated network namespace
        subprocess.run([
            'ip', 'netns', 'add', vm_name
        ])
        
        # Create virtual interfaces
        subprocess.run([
            'ip', 'link', 'add', f'veth-{vm_name}', 'type', 'veth',
            'peer', f'eth0-{vm_name}'
        ])
        
        # Move interface to namespace
        subprocess.run([
            'ip', 'link', 'set', f'eth0-{vm_name}',
            'netns', vm_name
        ])
```

## Resource Isolation

### 1. CPU Limits

```python
class ResourceLimiter:
    def set_cpu_limit(self, vm_name: str, cpu_count: int) -> None:
        """Set CPU limits for VM."""
        subprocess.run([
            'cpulimit',
            '--pid', self.get_vm_pid(vm_name),
            '--limit', str(cpu_count * 100)
        ])
```

### 2. Memory Limits

```python
    def set_memory_limit(
        self,
        vm_name: str,
        memory_gb: int
    ) -> None:
        """Set memory limits for VM."""
        memory_bytes = memory_gb * 1024 * 1024 * 1024
        subprocess.run([
            'cgroup-tools', 'set',
            '--memory', str(memory_bytes),
            vm_name
        ])
```

## Security Best Practices

1. **Advertisement Security**
   - Advertisements expire after 5 minutes
   - All advertisements must be signed
   - Provider IDs are derived from public keys

2. **SSH Security**
   - Use ED25519 keys for better security
   - Proper file permissions (600 for private, 644 for public)
   - One key pair per VM
   - No password authentication allowed

3. **Network Security**
   - Regular port verification
   - Network isolation between VMs
   - Rate limiting on all APIs
   - TLS for all HTTP communication

4. **Resource Security**
   - Strict resource limits per VM
   - Resource monitoring and alerts
   - Automatic cleanup of unused resources

## Security Checklist

### Provider Setup
- [ ] Generate provider identity (key pair)
- [ ] Verify all required ports
- [ ] Setup network isolation
- [ ] Configure resource limits
- [ ] Enable monitoring

### Requestor Setup
- [ ] Generate SSH key pair
- [ ] Verify provider signatures
- [ ] Use secure storage for keys
- [ ] Monitor VM resource usage

### VM Creation
- [ ] Verify provider authenticity
- [ ] Create isolated network namespace
- [ ] Set resource limits
- [ ] Provision SSH keys securely
- [ ] Verify VM accessibility

## Incident Response

1. **Advertisement Abuse**
   - Immediately remove invalid advertisements
   - Block provider ID
   - Alert other providers

2. **Resource Abuse**
   - Terminate affected VMs
   - Block abusive requestors
   - Restore resource limits

3. **Network Issues**
   - Isolate affected VMs
   - Reset network configurations
   - Update firewall rules

This document will be updated as security measures evolve and new threats are identified.
