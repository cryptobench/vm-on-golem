# VM on Golem Requestor

A simple CLI tool for managing VMs on the Golem Network.

## Installation

```bash
# Clone the repository
git clone https://github.com/golem/vm-on-golem.git
cd vm-on-golem/requestor-server

# Install using pip
pip install -e .
```

## Usage

### Create a VM
```bash
# Create a small VM
golem vm create my-webserver --size small

# Create a medium VM in a specific country
golem vm create my-app --size medium --country SE
```

### List VMs
```bash
golem vm list
```

### SSH into a VM
```bash
golem vm ssh my-webserver
```

### Start/Stop a VM
```bash
# Start a VM
golem vm start my-webserver

# Stop a VM
golem vm stop my-webserver
```

### Destroy a VM
```bash
golem vm destroy my-webserver
```

## VM Sizes

The following predefined VM sizes are available:

- `small`: 1 CPU, 1GB RAM, 10GB storage
- `medium`: 2 CPU, 4GB RAM, 20GB storage
- `large`: 4 CPU, 8GB RAM, 40GB storage
- `xlarge`: 8 CPU, 16GB RAM, 80GB storage

## Configuration

The requestor uses the following configuration files and directories:

- SSH Keys: `~/.golem/ssh/`
- Database: `~/.golem/vms.db`
- Config Directory: `~/.golem/`

Environment variables can be used to override default settings:

```bash
# Discovery service URL
export GOLEM_REQUESTOR_DISCOVERY_URL="http://discovery.golem.network:7465"

# Custom SSH key directory
export GOLEM_REQUESTOR_SSH_KEY_DIR="/path/to/keys"

# Custom database path
export GOLEM_REQUESTOR_DB_PATH="/path/to/database.db"
```

## Development

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_provider.py

# Run with coverage
pytest --cov=golem_requestor
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
