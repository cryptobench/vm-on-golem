# VM on Golem Discovery Server

The Discovery Server acts as a central advertisement board for the VM on Golem platform, enabling providers to advertise their available resources and requestors to find suitable providers.

## Features

- Simple advertisement board for VM providers
- Resource-based provider discovery
- Automatic cleanup of stale advertisements (5-minute expiry)
- Rate limiting protection
- SQLite database for easy deployment
- Async API with FastAPI

## Installation

1. Ensure you have Python 3.9 or later installed
2. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Clone the repository and install dependencies:
   ```bash
   cd discovery-server
   poetry install
   ```

## Configuration

The server can be configured through environment variables:

```bash
# API Settings
export GOLEM_DISCOVERY_DEBUG=false
export GOLEM_DISCOVERY_HOST="0.0.0.0"
export GOLEM_DISCOVERY_PORT=7465

# Database Settings (SQLite)
export GOLEM_DISCOVERY_DATABASE_DIR="~/.golem/discovery"
export GOLEM_DISCOVERY_DATABASE_NAME="discovery.db"

# Rate Limiting
export GOLEM_DISCOVERY_RATE_LIMIT_PER_MINUTE=100
```

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

### Post an Advertisement (Provider)

```bash
curl -X POST http://localhost:7465/api/v1/advertisements \
  -H "Content-Type: application/json" \
  -H "X-Provider-ID: provider123" \
  -H "X-Provider-Signature: signature123" \
  -d '{
    "ip_address": "83.233.10.2",
    "country": "SE",
    "resources": {
      "cpu": 4,
      "memory": 8,
      "storage": 100
    }
  }'
```

### Find Providers (Requestor)

```bash
# Find providers with at least 2 CPU cores and 4GB memory
curl "http://localhost:7465/api/v1/advertisements?cpu=2&memory=4"

# Find providers in Sweden
curl "http://localhost:7465/api/v1/advertisements?country=SE"
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

## API Documentation

Full API documentation is available in the [api-reference.md](../docs/api-reference.md) file.

## Architecture

The Discovery Server follows a clean architecture pattern:

```
discovery/
├── api/            # API layer (FastAPI routes and models)
├── db/             # Database layer (SQLAlchemy models and repository)
└── config.py       # Configuration management
```

Key components:
- FastAPI for the REST API
- SQLite for the database (stored in ~/.golem/discovery)
- SQLAlchemy for ORM
- Pydantic for data validation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests
5. Submit a pull request

## License

This project is part of the Golem Network and is licensed under the GPL-3.0 license.
