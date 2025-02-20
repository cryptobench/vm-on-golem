# Golem VM Discovery Server

The Discovery Server acts as the central hub for the Golem Network, enabling requestors to find providers with matching resources.

## Installation

```bash
pip install golem-vm-discovery
```

## Running the Server

The Discovery Server comes with sensible defaults and can be run immediately after installation:

```bash
golem-discovery
```

The server will start with the following default configuration:
- Listen on all interfaces (0.0.0.0) port 7465
- Store data in SQLite at ~/.golem/discovery/discovery.db
- Rate limit to 100 requests per minute per IP
- Clean up expired advertisements every minute
- Require provider advertisement refresh every 5 minutes

### Configuration

All settings have built-in defaults and can be optionally overridden using environment variables:

```bash
# Override only what you need:

# Change the port
GOLEM_DISCOVERY_PORT=8000

# Enable debug mode
GOLEM_DISCOVERY_DEBUG=true

# Use a different database location
GOLEM_DISCOVERY_DATABASE_DIR="/custom/path"
```

### Default Settings

| Setting | Default | Environment Variable | Description |
|---------|---------|---------------------|-------------|
| Host | 0.0.0.0 | GOLEM_DISCOVERY_HOST | Listen interface |
| Port | 7465 | GOLEM_DISCOVERY_PORT | Listen port |
| Debug | false | GOLEM_DISCOVERY_DEBUG | Enable debug mode |
| Database Dir | ~/.golem/discovery | GOLEM_DISCOVERY_DATABASE_DIR | Database directory |
| Database Name | discovery.db | GOLEM_DISCOVERY_DATABASE_NAME | Database filename |
| Rate Limit | 100 | GOLEM_DISCOVERY_RATE_LIMIT_PER_MINUTE | Requests per minute per IP |
| Ad Expiry | 5 | GOLEM_DISCOVERY_ADVERTISEMENT_EXPIRY_MINUTES | Minutes until ads expire |
| Cleanup Interval | 60 | GOLEM_DISCOVERY_CLEANUP_INTERVAL_SECONDS | Seconds between cleanups |

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /api/v1/advertisements` - List available providers
- `POST /api/v1/advertisements` - Register a provider

## Environment Variables

All settings can be configured through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| GOLEM_DISCOVERY_HOST | Server host | 0.0.0.0 |
| GOLEM_DISCOVERY_PORT | Server port | 7465 |
| GOLEM_DISCOVERY_DEBUG | Enable debug mode | false |
| GOLEM_DISCOVERY_DATABASE_DIR | Database directory | ~/.golem/discovery |
| GOLEM_DISCOVERY_DATABASE_NAME | Database filename | discovery.db |
| GOLEM_DISCOVERY_RATE_LIMIT_PER_MINUTE | Rate limit per IP | 100 |
| GOLEM_DISCOVERY_ADVERTISEMENT_EXPIRY_MINUTES | Advertisement TTL | 5 |
| GOLEM_DISCOVERY_CLEANUP_INTERVAL_SECONDS | Cleanup interval | 60 |

## Development

To run the server in development mode:

```bash
GOLEM_DISCOVERY_DEBUG=true golem-discovery
```

This will enable auto-reload on code changes and more detailed logging.
