# VM on Golem - Setup Guide

## Repository Structure

The VM on Golem project is split into three main repositories, each handling a specific component of the system. This guide outlines the structure and setup of each repository.

## 1. Provider Node Repository

### Repository: vm-on-golem-provider

```
vm-on-golem-provider/
├── golem_provider/
│   ├── __init__.py
│   ├── vm/                  # VM Management
│   │   ├── __init__.py
│   │   ├── multipass.py    # Multipass integration
│   │   ├── provider.py     # VM provider implementation
│   │   └── models.py       # VM-related data models
│   ├── api/                # REST API
│   │   ├── __init__.py
│   │   ├── server.py      # FastAPI server
│   │   ├── routes.py      # API endpoints
│   │   └── models.py      # API data models
│   ├── monitoring/         # Resource Monitoring
│   │   ├── __init__.py
│   │   └── resource_monitor.py
│   ├── network/           # Network Management
│   │   ├── __init__.py
│   │   └── port_verifier.py
│   └── security/          # Security Features
       ├── __init__.py
       └── ssh_manager.py
├── pyproject.toml         # Project configuration
└── README.md
```

### Dependencies

```toml
[tool.poetry]
name = "golem-vm-provider"
version = "0.1.0"
description = "VM on Golem Provider Node"

[tool.poetry.dependencies]
python = "^3.9"
fastapi = "^0.68.0"
uvicorn = "^0.15.0"
python-multipass = "^0.1.0"
pydantic = "^1.8.2"
cryptography = "^3.4.7"
asyncssh = "^2.7.0"
prometheus-client = "^0.11.0"
```

## 2. Requestor Node Repository

### Repository: vm-on-golem-requestor

```
vm-on-golem-requestor/
├── golem_requestor/
│   ├── __init__.py
│   ├── cli/               # CLI Interface
│   │   ├── __init__.py
│   │   ├── commands.py   # Click commands
│   │   └── models.py     # CLI data models
│   ├── vm/               # VM Operations
│   │   ├── __init__.py
│   │   ├── controller.py # VM management
│   │   └── models.py     # VM data models
│   ├── provider/         # Provider Integration
│   │   ├── __init__.py
│   │   ├── client.py     # Provider API client
│   │   └── selection.py  # Provider selection logic
│   ├── ssh/              # SSH Management
│   │   ├── __init__.py
│   │   └── manager.py    # SSH key management
│   └── config/           # Configuration
       ├── __init__.py
       └── manager.py     # Config management
├── pyproject.toml        # Project configuration
└── README.md
```

### Dependencies

```toml
[tool.poetry]
name = "golem-vm-requestor"
version = "0.1.0"
description = "VM on Golem Requestor CLI"

[tool.poetry.dependencies]
python = "^3.9"
click = "^8.0.1"
pydantic = "^1.8.2"
cryptography = "^3.4.7"
asyncssh = "^2.7.0"
aiohttp = "^3.7.4"

[tool.poetry.scripts]
golem = "golem_requestor.cli.commands:cli"
```

## 3. Discovery Service Repository

### Repository: vm-on-golem-discovery

```
vm-on-golem-discovery/
├── golem_discovery/
│   ├── __init__.py
│   ├── api/              # REST API
│   │   ├── __init__.py
│   │   ├── server.py    # FastAPI server
│   │   ├── routes.py    # API endpoints
│   │   └── models.py    # API data models
│   ├── db/              # Database
│   │   ├── __init__.py
│   │   ├── models.py    # SQLAlchemy models
│   │   └── repository.py # Repository pattern
│   ├── service/         # Core Service
│   │   ├── __init__.py
│   │   └── manager.py   # Service management
│   └── security/        # Security
       ├── __init__.py
       └── auth.py       # Authentication
├── alembic/             # Database Migrations
│   ├── versions/
│   └── env.py
├── alembic.ini          # Alembic configuration
├── pyproject.toml       # Project configuration
└── README.md
```

### Dependencies

```toml
[tool.poetry]
name = "golem-vm-discovery"
version = "0.1.0"
description = "VM on Golem Discovery Service"

[tool.poetry.dependencies]
python = "^3.9"
fastapi = "^0.68.0"
uvicorn = "^0.15.0"
sqlalchemy = "^1.4.23"
alembic = "^1.7.1"
asyncpg = "^0.24.0"
pydantic = "^1.8.2"
prometheus-client = "^0.11.0"
```

## Setup Instructions

### 1. Provider Node Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/golem/vm-on-golem-provider.git
   cd vm-on-golem-provider
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Verify Multipass installation:
   ```bash
   multipass version
   ```

### 2. Requestor Node Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/golem/vm-on-golem-requestor.git
   cd vm-on-golem-requestor
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Initialize configuration:
   ```bash
   golem init
   ```

### 3. Discovery Service Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/golem/vm-on-golem-discovery.git
   cd vm-on-golem-discovery
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Configure database:
   ```bash
   cp .env.example .env
   # Edit .env with database credentials
   ```

4. Run migrations:
   ```bash
   alembic upgrade head
   ```

## Development Workflow

1. Each component can be developed independently
2. Use Poetry for dependency management
3. Follow the API specifications in api-reference.md
4. Implement security measures from security-guide.md
5. Follow error handling patterns from technical-spec.md

## Implementation Notes

1. **Provider Node**
   - Implements VM management through Multipass
   - Exposes REST API for VM operations
   - Handles SSH key provisioning
   - Monitors system resources

2. **Requestor Node**
   - Provides CLI interface for VM management
   - Handles provider selection
   - Manages SSH keys
   - Implements configuration persistence

3. **Discovery Service**
   - Manages provider registration
   - Handles resource discovery
   - Implements provider health checks
   - Provides resource allocation APIs

## Next Steps

1. Implement core functionality in each repository
2. Follow the technical specifications in technical-spec.md
3. Implement security measures from security-guide.md
4. Develop API endpoints according to api-reference.md
5. Create comprehensive tests for each component

This setup guide should be used in conjunction with:
- api-reference.md
- technical-spec.md
- security-guide.md
- provider-implementation.md
- requestor-implementation.md
- discovery-implementation.md
