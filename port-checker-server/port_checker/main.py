import asyncio
import logging
from typing import List, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Golem Port Checker")

class PortCheckRequest(BaseModel):
    """Request model for port checking."""
    provider_ip: str = Field(..., description="Provider's public IP address")
    ports: List[int] = Field(..., description="List of ports to check")

    @validator('ports')
    def validate_ports(cls, ports):
        """Validate port numbers."""
        for port in ports:
            if not 1 <= port <= 65535:
                raise ValueError(f"Invalid port number: {port}")
        return ports

class PortStatus(BaseModel):
    """Status of a single port."""
    accessible: bool = Field(..., description="Whether the port is accessible")
    error: str = Field(None, description="Error message if port is not accessible")

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
