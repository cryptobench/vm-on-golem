# Golem Port Checker Service

A service that verifies port accessibility for Golem providers. This service is used to ensure that providers have the necessary ports open and accessible before they can advertise their services on the Golem Network.

## Features

- Verifies port accessibility through TCP connection attempts
- Concurrent port checking for faster results
- Simple REST API interface
- Health check endpoint
- Configurable through environment variables

## Installation

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

## Configuration

The service can be configured using environment variables or a `.env` file:

```env
PORT_CHECKER_HOST=0.0.0.0      # Host to bind to
PORT_CHECKER_PORT=7466         # Port to listen on
PORT_CHECKER_DEBUG=false       # Enable debug mode
```

## Running the Service

1. Start the service:
```bash
poetry run python run.py
```

2. The service will start on the configured host and port (default: http://0.0.0.0:7466)

## API Endpoints

### Check Ports

`POST /check-ports`

Check accessibility of specified ports for a provider.

Request body:
```json
{
  "provider_ip": "192.168.1.100",
  "ports": [7466, 50800, 50801]
}
```

Response:
```json
{
  "success": true,
  "results": {
    "7466": {
      "accessible": true,
      "error": null
    },
    "50800": {
      "accessible": true,
      "error": null
    },
    "50801": {
      "accessible": false,
      "error": "Connection refused"
    }
  },
  "message": "Successfully verified 2 out of 3 ports"
}
```

### Health Check

`GET /health`

Check if the service is running.

Response:
```json
{
  "status": "ok"
}
```

## Development

1. Enable debug mode for auto-reload:
```bash
PORT_CHECKER_DEBUG=true poetry run python run.py
```

2. Run tests:
```bash
poetry run pytest
```

## Integration with Golem Provider

The port checker service is used by Golem providers to verify their port accessibility before advertising on the network. Providers will:

1. Try to bind to required ports locally (7466 and range 50800-50900)
2. Use this service to verify external accessibility of successfully bound ports
3. Only advertise and use ports that are verified as accessible

This ensures that providers only advertise ports that are truly accessible from the internet, preventing connection issues for requestors.
