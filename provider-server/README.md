# VM on Golem Provider Node

The Provider Node is responsible for managing virtual machines (VMs) on the Golem Network. It handles:
- VM lifecycle management using Multipass
- Resource advertisement to the discovery service
- SSH key provisioning
- Resource monitoring and allocation

## Features

- Simple VM management through REST API
- Automatic resource advertisement
- Resource monitoring and thresholds
- Rate limiting protection
- SSH key management
- Support for multiple VM sizes

## Prerequisites

1. Python 3.9 or later
2. Multipass installed and configured
3. Poetry for dependency management
4. Sufficient system resources for VM hosting

## Installation

1. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Clone the repository and install dependencies:
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
GOLEM_PROVIDER_PORT=7465

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
```

See the `.env` file for all available configuration options.

## Running the Server

1. Start the server:
   ```bash
   ./run.py
   ```

   Or using Poetry:
   ```bash
   poetry run python run.py
   ```

2. The server will be available at http://localhost:7465
3. API documentation will be available at http://localhost:7465/api/v1/docs

## API Usage Examples

### Create a VM

```bash
curl -X POST http://localhost:7465/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-webserver",
    "size": "small"
  }'
```

### Add SSH Key to VM

```bash
curl -X POST http://localhost:7465/api/v1/vms/{vm_id}/ssh-keys \
  -H "Content-Type: application/json" \
  -d '{
    "name": "default",
    "public_key": "ssh-rsa AAAA..."
  }'
```

### List VMs

```bash
curl http://localhost:7465/api/v1/vms
```

### Get VM Status

```bash
curl http://localhost:7465/api/v1/vms/{vm_id}
```

## Development

### Running Tests

```bash
poetry run pytest
```

### Code Style

The project uses Black for code formatting and isort for import sorting:

```bash
poetry run black .
poetry run isort .
```

## Architecture

The Provider Node follows a clean architecture pattern:

```
provider/
├── api/            # API layer (FastAPI routes and models)
├── vm/             # VM management layer (Multipass integration)
├── discovery/      # Resource advertisement
└── config.py       # Configuration management
```

Key components:
- FastAPI for the REST API
- Multipass for VM management
- Resource monitoring with psutil
- Automatic advertisement to discovery service

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
