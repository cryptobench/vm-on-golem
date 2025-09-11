# VM on Golem Port Checker Server

The Port Checker Server provides a critical network verification service for the Golem Network, ensuring providers have proper port accessibility before joining the network. It verifies both local and external port accessibility through a simple REST API.

## System Architecture

```mermaid
graph TB
    subgraph Port Checker
        API[FastAPI Service]
        Check[Port Checker]
        Rate[Rate Limiter]
    end
    
    subgraph Providers
        P1[Provider 1]
        P2[Provider 2]
    end
    
    P1 & P2 -->|Verify Ports| API
    API --> Check
    Rate -->|Protect| API
```

## How It Works

### Port Verification Flow

```mermaid
sequenceDiagram
    participant P as Provider
    participant PC as Port Checker
    
    P->>PC: Request Port Check
    PC->>PC: Verify Local Binding
    PC->>PC: Test External Access
    PC-->>P: Verification Results
    Note over PC: Multiple retries with delay
```

The port checker service verifies port accessibility through:
1. TCP connection attempts to specified ports
2. Retry mechanism with configurable attempts
3. Detailed error reporting
4. Concurrent port checking

## Installation

```bash
# Clone the repository
git clone https://github.com/golem/vm-on-golem.git
cd vm-on-golem/port-checker-server

# Install dependencies
poetry install
```

## Configuration

The server can be configured through environment variables:

```bash
# Server Settings
PORT_CHECKER_HOST="0.0.0.0"
PORT_CHECKER_PORT=9000
PORT_CHECKER_DEBUG=false

# Port Check Settings
PORT_CHECK_RETRIES=3
PORT_CHECK_RETRY_DELAY=1.0
PORT_CHECK_TIMEOUT=5.0
```

## API Reference

### Check Ports

```bash
POST /check-ports
```

Request:
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

```bash
GET /health
```

Response:
```json
{
    "status": "ok"
}
```

### Proxy (optional)

```bash
ANY /proxy/{path}
```

There are two modes. For better security, use provider-based routing.

- Provider-based (recommended):
  - `ANY /proxy/provider/{provider_id}/{path}?port=<port>`
  - Headers:
  - `X-Proxy-Source: discovery|golem-base` (required; defaults to `golem-base` if omitted)
    - `X-Proxy-Token: <shared secret>` (required)
  - Resolves provider IP via Discovery (default in docs) or Golem Base and forwards over HTTP to `port` (default 80).

- Direct IP (optional, disabled by default):
  - `ANY /proxy/{path}` with headers:
    - `X-Forward-To: <ip>:<port>` (required)
    - `X-Forward-Protocol: http` (optional)
    - `X-Proxy-Token: <shared secret>` (required)
  - Enable with `PORT_CHECKER_PROXY_ALLOW_DIRECT_IP=true`.

Security controls:
- Target must be a public IP (private/loopback/link-local/multicast are rejected).
- Target port must be allowed (configurable via env; default `80,443,1024-65535`; set `*` to allow all).
- Max request body size is limited (default 2 MiB).
- Connection and read timeouts are enforced.

Environment variables:
- `PORT_CHECKER_PROXY_ENABLED` (default `true`)
- `PORT_CHECKER_PROXY_ALLOWED_PORTS` e.g. `80,443,10000-11000`
- `PORT_CHECKER_PROXY_MAX_BODY_BYTES` (default `2097152`)
- `PORT_CHECKER_PROXY_CONNECT_TIMEOUT` (seconds, default `5.0`)
- `PORT_CHECKER_PROXY_READ_TIMEOUT` (seconds, default `10.0`)
- `PORT_CHECKER_CORS_ORIGINS` (comma-separated, default `*`)
- `DISCOVERY_API_URL` (default `http://localhost:9001/api/v1`)
- `PORT_CHECKER_PROXY_ALLOW_DIRECT_IP` (default `false`)
 - `PORT_CHECKER_PROXY_TOKEN` (required to enable proxying)
  
Golem Base (default; if using `source=golem-base`):
- `GOLEM_BASE_RPC_URL` (required if not provided per-request)
- `GOLEM_BASE_WS_URL` (required if not provided per-request)
 - `GOLEM_PROVIDER_ENVIRONMENT` (optional; set `development` to prefer `dev_*` annotations)

Per-request overrides (headers):
- `X-Proxy-Golem-Base-Rpc`: override RPC URL for this request
- `X-Proxy-Golem-Base-Ws`: override WS URL for this request

Forwarded tracing headers to providers:
- `X-Forwarded-For` includes the original client IP (appends to chain)
- `X-Real-IP` set to the immediate client IP

Examples:
```bash
# Provider-based (Discovery)
curl -i \
  -H "X-Proxy-Source: discovery" \
  -H "X-Proxy-Token: $TOKEN" \
  "http://localhost:9000/proxy/provider/PROVIDER123/status?port=8080"

# Provider-based (Golem Base)
curl -i \
  -H "X-Proxy-Source: golem-base" \
  -H "X-Proxy-Token: $TOKEN" \
  "http://localhost:9000/proxy/provider/PROVIDER123/status?port=8080"

# Direct IP (if explicitly enabled)
curl -i \
  -H "X-Forward-To: 203.0.113.42:8080" \
  -H "X-Forward-Protocol: http" \
  -H "X-Proxy-Token: $TOKEN" \
  "http://localhost:9000/proxy/status"
```

## Technical Details

### Port Verification Process

1. **Request Validation**
   - Valid IP address format
   - Port numbers within range (1-65535)
   - Maximum ports per request

2. **Verification Steps**
   - TCP connection attempt
   - Configurable timeout
   - Multiple retry attempts
   - Delay between retries

3. **Response Details**
   - Per-port accessibility status
   - Detailed error messages
   - Overall success indicator
   - Summary message

### Error Handling

The API uses standardized error responses:

```json
{
    "detail": {
        "code": "ERROR_CODE",
        "message": "Human readable message"
    }
}
```

Common error codes:
- `INVALID_IP`: Invalid IP address format
- `INVALID_PORT`: Port number out of range
- `CHECK_FAILED`: Port check operation failed

## Running the Server

### Manual Start

```bash
# Start the server
poetry run python run.py

# The server will be available at:
# - API: http://localhost:9000
# - Health Check: http://localhost:9000/health
# - OpenAPI Docs: http://localhost:9000/docs
```

### Running as a Systemd Service

The port checker can run as a systemd service for automatic startup and restart:

1. Install the service file:
```bash
sudo cp golem-port-checker.service /etc/systemd/system/
sudo systemctl daemon-reload
```

2. (Optional) Configure environment variables:
```bash
# Create environment file if you need custom settings
sudo mkdir -p /etc/golem
sudo nano /etc/golem/port-checker.env

# Example environment variables:
PORT_CHECKER_HOST=0.0.0.0
PORT_CHECKER_PORT=9000
PORT_CHECKER_DEBUG=false
```

3. Enable and start the service:
```bash
sudo systemctl enable golem-port-checker
sudo systemctl start golem-port-checker
```

4. Check service status:
```bash
sudo systemctl status golem-port-checker
```

5. View service logs:
```bash
# View all logs
sudo journalctl -u golem-port-checker

# Follow new logs
sudo journalctl -u golem-port-checker -f
```

The service is configured to:
- Start automatically on system boot
- Restart automatically if it crashes
- Log output to systemd journal

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests
5. Submit a pull request
