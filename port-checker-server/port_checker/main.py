import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple
from ipaddress import ip_address, IPv4Address, IPv6Address

from fastapi import FastAPI, HTTPException, Request, Response, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Golem Port Checker")

# CORS configuration (can be restricted via env)
ALLOW_ORIGINS = os.getenv("PORT_CHECKER_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOW_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Proxy configuration
PROXY_ENABLED = os.getenv("PORT_CHECKER_PROXY_ENABLED", "true").lower() == "true"
PROXY_ALLOW_DIRECT_IP = os.getenv("PORT_CHECKER_PROXY_ALLOW_DIRECT_IP", "false").lower() == "true"
MAX_BODY_BYTES = int(os.getenv("PORT_CHECKER_PROXY_MAX_BODY_BYTES", str(2 * 1024 * 1024)))  # 2 MiB
DEFAULT_ALLOWED_PORTS = "80,443,1024-65535"
ALLOWED_PORTS_SPEC = os.getenv("PORT_CHECKER_PROXY_ALLOWED_PORTS", DEFAULT_ALLOWED_PORTS)
CONNECT_TIMEOUT = float(os.getenv("PORT_CHECKER_PROXY_CONNECT_TIMEOUT", "5.0"))
READ_TIMEOUT = float(os.getenv("PORT_CHECKER_PROXY_READ_TIMEOUT", "10.0"))
DISCOVERY_API_URL = os.getenv("DISCOVERY_API_URL", "http://localhost:9001/api/v1")
PROXY_SHARED_TOKEN = os.getenv("PORT_CHECKER_PROXY_TOKEN", "")
GOLEM_BASE_RPC_URL = os.getenv("GOLEM_BASE_RPC_URL", "")
GOLEM_BASE_WS_URL = os.getenv("GOLEM_BASE_WS_URL", "")
# Dev mode flag: prefer dev_ annotation keys when resolving on-chain adverts
PROVIDER_ENV = os.getenv("GOLEM_PROVIDER_ENVIRONMENT", "").lower()
IS_PROVIDER_DEV = PROVIDER_ENV == "development"
# Align expected network with provider env: dev → testnet, else mainnet
EXPECTED_NETWORK = "testnet" if IS_PROVIDER_DEV else "mainnet"
# Allow local/private IPs when developing or when explicitly enabled. This keeps
# production safe-by-default while unblocking localhost/private-net workflows.
ALLOW_LOCAL_IPS = os.getenv("PORT_CHECKER_ALLOW_LOCAL_IPS", "false").lower() == "true"
ALLOW_LOCAL_IPS = ALLOW_LOCAL_IPS or IS_PROVIDER_DEV

# Compatibility shim for web3 provider symbol changes:
# Some versions of web3 expose `WebsocketProvider` (lowercase 's') while
# golem-base-sdk imports `WebSocketProvider` (uppercase 'S'). If the SDK is
# present alongside a newer/older web3, the import may fail. To improve
# robustness, alias the symbol when possible before importing the SDK.
try:  # pragma: no cover - environment-specific import guard
    import web3 as _web3  # type: ignore
    if not hasattr(_web3, "WebSocketProvider") and hasattr(_web3, "WebsocketProvider"):
        setattr(_web3, "WebSocketProvider", getattr(_web3, "WebsocketProvider"))
except Exception:  # pragma: no cover - best-effort shim
    pass

try:
    # Prefer read-only client for provider lookups
    try:
        from golem_base_sdk import GolemBaseROClient as _GolemBaseROClient  # type: ignore
    except Exception:  # pragma: no cover - SDK variants
        _GolemBaseROClient = None  # type: ignore

    from golem_base_sdk import GolemBaseClient  # type: ignore
    from golem_base_sdk.types import EntityKey, GenericBytes  # type: ignore
    _HAS_GOLEM_BASE = True
except Exception:  # pragma: no cover - optional
    GolemBaseClient = None  # type: ignore
    EntityKey = None  # type: ignore
    GenericBytes = None  # type: ignore
    _HAS_GOLEM_BASE = False


# Note: Golem Base SDK is an explicit package dependency. If it's not available
# at runtime, the proxy will respond with 501 for Golem Base lookups.


def _parse_allowed_ports(spec: str) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    s = (spec or "").strip()
    if s == "*":
        return [(1, 65535)]
    for part in (p.strip() for p in spec.split(",") if p.strip()):
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError:
                continue
            if 1 <= start <= 65535 and 1 <= end <= 65535 and start <= end:
                ranges.append((start, end))
        else:
            try:
                port = int(part)
            except ValueError:
                continue
            if 1 <= port <= 65535:
                ranges.append((port, port))
    return ranges or [(80, 80), (443, 443)]


ALLOWED_PORT_RANGES = _parse_allowed_ports(ALLOWED_PORTS_SPEC)


def _is_allowed_port(port: int) -> bool:
    for start, end in ALLOWED_PORT_RANGES:
        if start <= port <= end:
            return True
    return False


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ip_address(ip_str)
    except ValueError:
        return False
    if isinstance(ip, (IPv4Address, IPv6Address)):
        # Disallow private, loopback, link-local, multicast, reserved
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True

class PortCheckRequest(BaseModel):
    """Request model for port checking."""
    provider_ip: str = Field(..., description="Provider's public IP address")
    ports: List[int] = Field(..., description="List of ports to check")

    @field_validator('ports')
    def validate_ports(cls, ports):
        """Validate port numbers."""
        for port in ports:
            if not 1 <= port <= 65535:
                raise ValueError(f"Invalid port number: {port}")
        return ports

class PortStatus(BaseModel):
    """Status of a single port."""
    accessible: bool = Field(..., description="Whether the port is accessible")
    error: Optional[str] = Field(None, description="Error message if port is not accessible")

class PortCheckResponse(BaseModel):
    """Response model for port checking."""
    success: bool = Field(..., description="Overall success status")
    results: Dict[int, PortStatus] = Field(..., description="Results for each port")
    message: str = Field(..., description="Summary message")

async def check_port(ip: str, port: int, retries: int = 3, retry_delay: float = 1.0) -> PortStatus:
    """Check if a port is accessible with retries.
    
    Args:
        ip: IP address to check
        port: Port number to check
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        PortStatus object with accessibility result
    """
    last_error = None
    
    for attempt in range(retries):
        try:
            # Try to establish a TCP connection
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            
            logger.info(f"Port {port} is accessible (attempt {attempt + 1}/{retries})")
            return PortStatus(
                accessible=True,
                error=None
            )
        except asyncio.TimeoutError:
            last_error = "Connection timed out"
            logger.warning(f"Port {port} timed out (attempt {attempt + 1}/{retries})")
        except ConnectionRefusedError:
            last_error = "Connection refused"
            logger.warning(f"Port {port} connection refused (attempt {attempt + 1}/{retries})")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Error checking port {port} (attempt {attempt + 1}/{retries}): {last_error}")
        
        if attempt < retries - 1:
            await asyncio.sleep(retry_delay)
    
    return PortStatus(
        accessible=False,
        error=last_error
    )

@app.post("/check-ports", response_model=PortCheckResponse)
async def check_ports(request: PortCheckRequest) -> PortCheckResponse:
    """Check accessibility of specified ports.
    
    Args:
        request: Port check request containing IP and ports to check
        
    Returns:
        Results of port checking
    """
    logger.info(f"Checking ports {request.ports} for IP {request.provider_ip}")
    
    # Check all ports concurrently
    tasks = [
        check_port(request.provider_ip, port)
        for port in request.ports
    ]
    results = await asyncio.gather(*tasks)
    
    # Compile results
    port_results = {
        port: status
        for port, status in zip(request.ports, results)
    }
    
    # Count accessible ports
    accessible_ports = sum(1 for status in results if status.accessible)
    
    # Print detailed results
    logger.info("Port check results:")
    for port, status in port_results.items():
        if status.accessible:
            logger.info(f"Port {port}: ✅ Accessible")
        else:
            logger.info(f"Port {port}: ❌ Not accessible - {status.error}")
    
    response = PortCheckResponse(
        success=accessible_ports > 0,
        results=port_results,
        message=f"Successfully verified {accessible_ports} out of {len(request.ports)} ports"
    )
    
    logger.info(f"Summary: {response.message}")
    return response

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.api_route("/proxy/provider/{provider_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def http_proxy_provider(
    request: Request,
    provider_id: str,
    path: str,
    port: Optional[int] = Query(default=80),
    x_proxy_source: Optional[str] = Header(default=None),
    x_proxy_token: Optional[str] = Header(default=None),
    x_proxy_golem_base_rpc: Optional[str] = Header(default=None),
    x_proxy_golem_base_ws: Optional[str] = Header(default=None),
) -> Response:
    """Proxy to a provider resolved by provider_id via the discovery service.

    - Resolves IP using DISCOVERY_API_URL `/advertisements/{provider_id}`.
    - Only supports `http` to the provider (providers typically do not serve HTTPS).
    - Port defaults to 80; may be overridden with `?port=NNNN` but must be in allowed range.
    """
    if not PROXY_ENABLED:
        raise HTTPException(status_code=404, detail="Proxy is disabled")
    if not PROXY_SHARED_TOKEN or x_proxy_token != PROXY_SHARED_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Validate port
    if port is None or not _is_allowed_port(int(port)):
        raise HTTPException(status_code=403, detail="Target port not allowed")

    # Resolve IP from source; default to Golem Base
    src = (x_proxy_source or "golem-base").lower()
    if src not in {"discovery", "golem-base"}:
        raise HTTPException(status_code=400, detail="Invalid source; use 'discovery' or 'golem-base'")

    ip: Optional[str] = None
    if src == "discovery":
        adv_url = f"{DISCOVERY_API_URL.rstrip('/')}/advertisements/{provider_id}"
        timeout = aiohttp.ClientTimeout(total=None, connect=CONNECT_TIMEOUT, sock_read=READ_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(adv_url) as adv_resp:
                    if adv_resp.status != 200:
                        raise HTTPException(status_code=404, detail="Provider not found")
                    data = await adv_resp.json()
                    ip = data.get("ip_address") if isinstance(data, dict) else None
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="Discovery timeout")
            except aiohttp.ClientError as e:
                raise HTTPException(status_code=502, detail=f"Discovery error: {e}")
    else:
        if not _HAS_GOLEM_BASE:
            raise HTTPException(status_code=501, detail="Golem Base support not installed on server")
        rpc_url = (x_proxy_golem_base_rpc or GOLEM_BASE_RPC_URL).strip()
        ws_url = (x_proxy_golem_base_ws or GOLEM_BASE_WS_URL).strip()
        if not rpc_url or not ws_url:
            raise HTTPException(status_code=500, detail="Golem Base RPC/WS URLs not configured")
        try:
            # Build client (read-only). Prefer RO client if available.
            kwargs = {"rpc_url": rpc_url, "ws_url": ws_url}
            client = None
            if '_GolemBaseROClient' in globals() and _GolemBaseROClient is not None:
                client = await _GolemBaseROClient.create_ro_client(**kwargs)  # type: ignore
            elif hasattr(GolemBaseClient, 'create_ro_client'):
                client = await GolemBaseClient.create_ro_client(**kwargs)  # type: ignore[attr-defined]
            elif hasattr(GolemBaseClient, 'create'):
                # Legacy path – some SDKs supported create(rpc_url, ws_url) without key
                client = await GolemBaseClient.create(**kwargs)  # type: ignore
            else:
                raise RuntimeError("No suitable Golem Base client constructor found")
            # Prefer dev_golem_provider_id in dev; always constrain by expected network
            net_clause = f' && golem_network="{EXPECTED_NETWORK}"'
            queries: List[str] = [f'golem_provider_id="{provider_id}"{net_clause}']
            if IS_PROVIDER_DEV:
                queries = [f'dev_golem_provider_id="{provider_id}"{net_clause}'] + queries
            results = []
            for q in queries:
                results = await client.query_entities(q)
                if results:
                    break
            if not results:
                await client.disconnect()
                raise HTTPException(status_code=404, detail="Provider not found on Golem Base")
            ek = EntityKey(GenericBytes.from_hex_string(results[0].entity_key))  # type: ignore
            md = await client.get_entity_metadata(ek)
            await client.disconnect()
            anns = {a.key: a.value for a in md.string_annotations}
            # Prefer dev_ prefixed keys in development; fall back to standard keys
            def pick(key: str) -> Optional[str]:
                if IS_PROVIDER_DEV and ("dev_" + key) in anns and str(anns["dev_" + key]).strip():
                    return str(anns["dev_" + key]).strip()
                v = anns.get(key)
                return str(v).strip() if v is not None else None
            ip = pick("golem_ip_address")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Golem Base error: {e}")
    if not ip:
        raise HTTPException(status_code=400, detail="Resolved IP invalid or not public")
    # In development, allow forwarding to local/private IPs to support local setups
    if not _is_public_ip(ip) and not ALLOW_LOCAL_IPS:
        raise HTTPException(status_code=400, detail="Resolved IP invalid or not public")

    # Build provider URL
    qs = request.url.query
    if qs:
        parts = [p for p in qs.split("&") if not p.startswith("port=")]
        qs_forward = "&".join(parts) if parts else ""
    else:
        qs_forward = ""
    url = f"http://{ip}:{int(port)}/{path}"
    if qs_forward:
        url = f"{url}?{qs_forward}"

    # Read body with size limit
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request body too large")

    hop_by_hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
        "accept-encoding",
    }
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}
    # Attach client IPs for tracing
    client_ip = request.client.host if request.client else ""
    prior_xff = request.headers.get("x-forwarded-for")
    chain = f"{prior_xff}, {client_ip}" if prior_xff and client_ip else (client_ip or prior_xff)
    if chain:
        fwd_headers["X-Forwarded-For"] = chain
    if client_ip:
        fwd_headers["X-Real-IP"] = client_ip

    timeout = aiohttp.ClientTimeout(total=None, connect=CONNECT_TIMEOUT, sock_read=READ_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.request(
                method=request.method,
                url=url,
                headers=fwd_headers,
                data=body if body else None,
                allow_redirects=False,
            ) as resp:
                content = await resp.read()
                resp_headers = {}
                for k, v in resp.headers.items():
                    if k.lower() in hop_by_hop:
                        continue
                    resp_headers[k] = v
                resp_headers["X-Proxy"] = "golem-port-checker"
                resp_headers["X-Proxy-Provider-Id"] = provider_id
                return Response(content=content, status_code=resp.status, headers=resp_headers)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Upstream timeout")
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")


@app.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def http_proxy(
    request: Request,
    path: str,
    x_forward_to: Optional[str] = Header(default=None),
    x_forward_protocol: Optional[str] = Header(default=None),
    x_proxy_token: Optional[str] = Header(default=None),
    target: Optional[str] = Query(default=None),
) -> Response:
    """Secure HTTP proxy to reach provider HTTP endpoints from HTTPS clients.

    Usage:
      - Set header `X-Forward-To: <ip>:<port>` (preferred), and optional `X-Forward-Protocol: http`.
      - Or provide query `?target=<ip>:<port>`.

    The proxy validates public IPs, allowed ports, request size and timeouts to avoid abuse.
    """
    if not PROXY_ENABLED:
        raise HTTPException(status_code=404, detail="Proxy is disabled")
    if not PROXY_SHARED_TOKEN or x_proxy_token != PROXY_SHARED_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Determine target host:port and protocol
    forward = (x_forward_to or target or "").strip()
    if not PROXY_ALLOW_DIRECT_IP:
        # Hardened default: do not allow direct IP forwarding
        raise HTTPException(status_code=404, detail="Direct IP proxying is disabled. Use /proxy/provider/{provider_id}/...")
    if not forward or ":" not in forward:
        raise HTTPException(status_code=400, detail="Missing X-Forward-To header or target query (expected <ip>:<port>)")

    host_part, port_part = forward.rsplit(":", 1)
    try:
        port = int(port_part)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid port in target")

    # In development, allow forwarding to local/private IPs to support local setups
    if not _is_public_ip(host_part) and not ALLOW_LOCAL_IPS:
        raise HTTPException(status_code=400, detail="Target must be a public IP address")

    if not _is_allowed_port(port):
        raise HTTPException(status_code=403, detail="Target port not allowed")

    protocol = (x_forward_protocol or "http").lower()
    if protocol not in {"http"}:  # explicit
        raise HTTPException(status_code=400, detail="Only 'http' protocol is supported")

    # Construct target URL, preserving query string except our own params
    qs = request.url.query
    if qs:
        # Remove our own 'target=' param from forwarded query string if present
        # Do a simple safe filter
        parts = [p for p in qs.split("&") if not p.startswith("target=")]
        qs_forward = "&".join(parts) if parts else ""
    else:
        qs_forward = ""

    url = f"{protocol}://{host_part}:{port}/{path}"
    if qs_forward:
        url = f"{url}?{qs_forward}"

    # Read body with size limit
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request body too large")

    # Prepare headers to forward (strip hop-by-hop and proxy-specific)
    hop_by_hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
        "accept-encoding",
        "x-forward-to",
        "x-forward-protocol",
    }
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}
    # Attach client IPs for tracing
    client_ip = request.client.host if request.client else ""
    prior_xff = request.headers.get("x-forwarded-for")
    chain = f"{prior_xff}, {client_ip}" if prior_xff and client_ip else (client_ip or prior_xff)
    if chain:
        fwd_headers["X-Forwarded-For"] = chain
    if client_ip:
        fwd_headers["X-Real-IP"] = client_ip

    timeout = aiohttp.ClientTimeout(total=None, connect=CONNECT_TIMEOUT, sock_read=READ_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.request(
                method=request.method,
                url=url,
                headers=fwd_headers,
                data=body if body else None,
                allow_redirects=False,
            ) as resp:
                content = await resp.read()
                # Sanitize response headers
                resp_headers = {}
                for k, v in resp.headers.items():
                    if k.lower() in hop_by_hop:
                        continue
                    resp_headers[k] = v
                resp_headers["X-Proxy"] = "golem-port-checker"
                return Response(content=content, status_code=resp.status, headers=resp_headers)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Upstream timeout")
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

def start():
    """Entry point for the port checker service."""
    import uvicorn
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    # Load environment variables
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)

    # Get configuration from environment
    host = os.getenv('PORT_CHECKER_HOST', '0.0.0.0')
    port = int(os.getenv('PORT_CHECKER_PORT', '9000'))  # Use 9000 by default to avoid conflict with provider port
    debug = os.getenv('PORT_CHECKER_DEBUG', 'false').lower() == 'true'

    # Configure uvicorn logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger.info(f"🚀 Starting port checker server on {host}:{port}")
    uvicorn.run(
        "port_checker.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="debug" if debug else "info",
        log_config=log_config,
        timeout_keep_alive=60,
        limit_concurrency=100,
    )

if __name__ == "__main__":
    start()
