# VM on Golem Provider Node

The Provider Node is responsible for managing virtual machines (VMs) on the Golem Network. It handles:
- VM lifecycle management using Multipass
- Resource advertisement to the discovery service
- SSH key provisioning
- Resource monitoring and allocation
- SSH proxy configuration via Nginx

## Features

- Simple VM management through REST API
- Automatic resource advertisement
- Resource monitoring and thresholds
- Rate limiting protection
- SSH key management
- Support for multiple VM sizes
- Secure SSH access via Nginx proxy

## Prerequisites

1. Python 3.9 or later
2. Multipass installed and configured
3. Poetry for dependency management
4. Nginx installed and configured
5. Sufficient system resources for VM hosting

## Installation

1. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install Nginx (on macOS):
   ```bash
   brew install nginx
   ```

3. Clone the repository and install dependencies:
   ```bash
   cd provider-server
   poetry install
   ```

## Configuration

The provider node can be configured through environment variables or a .env file:

```bash
# API Settings
GOLEM_PROVIDER_DEBUG=true
GOLEM_PROVIDER_HOST="0.0.0.0"
GOLEM_PROVIDER_PORT=7466

# Provider Settings
GOLEM_PROVIDER_ID="provider123"
GOLEM_PROVIDER_NAME="golem-provider"
GOLEM_PROVIDER_COUNTRY="SE"

# Discovery Service Settings
GOLEM_PROVIDER_DISCOVERY_URL="http://localhost:7465"
GOLEM_PROVIDER_ADVERTISEMENT_INTERVAL=240

# VM Settings
GOLEM_PROVIDER_MAX_VMS=10
GOLEM_PROVIDER_DEFAULT_VM_IMAGE="ubuntu:20.04"

# Nginx Settings
GOLEM_PROVIDER_NGINX_DIR="/opt/homebrew/etc/nginx"
GOLEM_PROVIDER_NGINX_CONFIG_DIR="/opt/homebrew/etc/nginx/golem.d"
GOLEM_PROVIDER_PORT_RANGE_START=50800
GOLEM_PROVIDER_PORT_RANGE_END=50900
GOLEM_PROVIDER_PUBLIC_IP="auto"  # Set to "auto" for automatic detection
```

See the `.env` file for all available configuration options.

## Running the Server

1. Start Nginx:
   ```bash
   brew services start nginx
   ```

2. Start the server:
   ```bash
   ./run.py
   ```

   Or using Poetry:
   ```bash
   poetry run python run.py
   ```

3. The server will be available at http://localhost:7466
4. API documentation will be available at http://localhost:7466/api/v1/docs

## API Usage Examples

### Create a VM

```bash
curl -X POST http://localhost:7466/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-webserver",
    "cpu_cores": 2,
    "memory_gb": 4,
    "storage_gb": 20
  }'
```

Response:
```json
{
  "id": "golem-my-webserver-20250219-130424",
  "name": "my-webserver",
  "status": "running",
  "ip_address": "192.168.64.2",
  "cpu_cores": 2,
  "memory_gb": 4,
  "storage_gb": 20,
  "proxy_port": 50800,
  "proxy_host": "localhost"
}
```

### Get VM Access Info

```bash
curl http://localhost:7466/api/v1/vms/{vm_id}/access
```

Response:
```json
{
  "ssh_host": "localhost",
  "ssh_port": 50800,
  "ssh_key": {
    "public_key": "ssh-ed25519 AAAA...",
    "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
  }
}
```

### List VMs

```bash
curl http://localhost:7466/api/v1/vms
```

### Get VM Status

```bash
curl http://localhost:7466/api/v1/vms/{vm_id}
```

## Architecture

The Provider Node follows a clean architecture pattern:

```
provider/
├── api/            # API layer (FastAPI routes and models)
├── vm/             # VM management layer
│   ├── multipass.py    # Multipass integration
│   ├── nginx_manager.py # Nginx proxy management
│   ├── port_manager.py  # Port allocation
│   └── cloud_init.py   # Cloud-init configuration
├── discovery/      # Resource advertisement
└── config.py      # Configuration management
```

Key components:
- FastAPI for the REST API
- Multipass for VM management
- Nginx for SSH proxying
- Resource monitoring with psutil
- Automatic advertisement to discovery service

## SSH Proxy Architecture

The provider uses Nginx to proxy SSH connections to VMs:

1. When a VM is created:
   - A unique port is allocated (50800-50900 range)
   - Nginx config is generated for the VM
   - SSH traffic to the allocated port is proxied to the VM's SSH port (22)

2. Benefits:
   - Secure access without exposing VM IPs
   - Port isolation between VMs
   - Connection management and logging
   - Automatic cleanup on VM termination

3. Configuration files:
   - Main config: /opt/homebrew/etc/nginx/nginx.conf
   - VM configs: /opt/homebrew/etc/nginx/golem.d/vm_*.conf

## Resource Management

The provider node monitors system resources and enforces thresholds:
- CPU usage threshold: 90%
- Memory usage threshold: 85%
- Storage usage threshold: 90%

When resources exceed these thresholds:
1. New VM creation requests are rejected
2. Resource advertisements are paused
3. Existing VMs continue running

## Security

1. **Resource Isolation**
   - VMs are isolated using Multipass
   - Resource limits are enforced per VM
   - Network isolation between VMs

2. **SSH Security**
   - Secure key provisioning
   - One key pair per VM
   - Proper file permissions
   - Traffic proxied through Nginx

3. **API Security**
   - Rate limiting protection
   - Input validation
   - Error handling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests
5. Submit a pull request

## License

This project is part of the Golem Network and is licensed under the GPL-3.0 license.
