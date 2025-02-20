import socket
import asyncio
import aiohttp
import logging
from typing import Set, List, Dict, Optional, Tuple
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)


@dataclass
class ServerAttempt:
    """Result of a single server's verification attempt."""
    server: str
    success: bool
    error: Optional[str] = None

@dataclass
class PortVerificationResult:
    """Result of port verification."""
    port: int
    accessible: bool
    error: str = None
    verified_by: str = None  # Server that successfully verified the port
    attempts: List[ServerAttempt] = None  # Track all server attempts

class PortVerifier:
    """Verifies port accessibility both locally and externally."""
    
    def __init__(self, port_check_servers: List[str], discovery_port: int = 7466):
        """Initialize port verifier.
        
        Args:
            port_check_servers: List of URLs for port checking services
            discovery_port: Port used for discovery service
        """
        self.port_check_servers = port_check_servers
        self.discovery_port = discovery_port
    
    async def verify_local_binding(self, ports: List[int]) -> Set[int]:
        """Try to bind to ports locally to verify availability.
        
        Args:
            ports: List of ports to verify
            
        Returns:
            Set of ports that were successfully bound
        """
        available_ports = set()
        temp_listeners = []
        
        for port in ports:
            try:
                # For discovery port, create a temporary TCP listener
                if port == self.discovery_port:
                    try:
                        server = await asyncio.start_server(
                            lambda r, w: None,  # Empty callback since we just need to listen
                            '0.0.0.0', 
                            port
                        )
                        temp_listeners.append(server)
                        available_ports.add(port)
                        logger.debug(f"Created temporary listener for discovery port {port}")
                        continue
                    except Exception as e:
                        if isinstance(e, OSError) and e.errno == 98:  # Address already in use
                            # This might be our own server starting up
                            available_ports.add(port)
                            logger.debug(f"Port {port} is already in use - this is expected if our server is starting")
                            continue
                        logger.debug(f"Failed to create temporary listener for discovery port {port}: {e}")
                        continue
                
                # For other ports, create a TCP listener
                try:
                    server = await asyncio.start_server(
                        lambda r, w: None,  # Empty callback since we just need to listen
                        '0.0.0.0', 
                        port
                    )
                    temp_listeners.append(server)
                    available_ports.add(port)
                    logger.debug(f"Created temporary listener on port {port}")
                except Exception as e:
                    if isinstance(e, OSError) and e.errno == 98:  # Address already in use
                        logger.debug(f"Port {port} is already in use")
                    else:
                        logger.debug(f"Failed to bind to port {port}: {e}")
                    continue
            except Exception as e:
                logger.debug(f"Failed to bind to port {port}: {e}")
                continue
        
        try:
            # Keep all temporary listeners active during verification
            yield available_ports
        finally:
            # Cleanup temporary listeners
            for server in temp_listeners:
                server.close()
                await server.wait_closed()
            if temp_listeners:
                logger.debug(f"Closed {len(temp_listeners)} temporary listeners")
    
    async def _get_public_ip(self) -> str:
        """Get public IP address using external service."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.ipify.org') as response:
                    return await response.text()
        except Exception as e:
            # Fallback to non-async request if aiohttp fails
            return requests.get('https://api.ipify.org').text
    
    async def verify_external_access(
        self, 
        ports: Set[int]
    ) -> Dict[int, PortVerificationResult]:
        """Verify external accessibility using port check servers.
        
        Args:
            ports: Set of ports to verify
            
        Returns:
            Dictionary mapping ports to their verification results
        """
        results = {}
        attempts = []
        
        # Try each server
        for server in self.port_check_servers:
            try:
                public_ip = await self._get_public_ip()
                
                async with aiohttp.ClientSession() as session:
                    response = await session.post(
                        f"{server}/check-ports",
                        json={
                            "provider_ip": public_ip,
                            "ports": list(ports)
                        },
                        timeout=30  # 30 second timeout for port checking
                    )
                    
                    if response.status == 200:
                        data = await response.json()
                        if data["success"]:
                            # Convert server results to PortVerificationResult objects
                            for port_str, result in data["results"].items():
                                port = int(port_str)
                                if port not in results or not results[port].accessible:
                                    # Only update if we haven't found a successful verification yet
                                    results[port] = PortVerificationResult(
                                        port=port,
                                        accessible=result["accessible"],
                                        error=result.get("error"),
                                        verified_by=server if result["accessible"] else None,
                                        attempts=[]  # Will be filled at the end
                                    )
                            attempts.append(ServerAttempt(server=server, success=True))
                            logger.info(f"Port verification completed using {server}")
                        else:
                            attempts.append(ServerAttempt(
                                server=server,
                                success=False,
                                error="Server returned unsuccessful response"
                            ))
                    else:
                        attempts.append(ServerAttempt(
                            server=server,
                            success=False,
                            error=f"Server returned status {response.status}"
                        ))
            except asyncio.TimeoutError:
                attempts.append(ServerAttempt(
                    server=server,
                    success=False,
                    error="Connection timed out"
                ))
                logger.warning(f"Timeout while verifying ports with {server}")
            except Exception as e:
                attempts.append(ServerAttempt(
                    server=server,
                    success=False,
                    error=str(e)
                ))
                logger.warning(f"Failed to verify ports with {server}: {e}")
        
        # If no successful verifications, mark all ports as inaccessible
        if not any(result.accessible for result in results.values()):
            logger.error("Failed to verify ports with any server")
            results = {
                port: PortVerificationResult(
                    port=port,
                    accessible=False,
                    error="Failed to verify with any port check server",
                    attempts=[]  # Will be filled below
                )
                for port in ports
            }
        
        # Add attempts to all results
        for result in results.values():
            result.attempts = attempts
        
        return results
    
    async def _create_temp_listener(self, port: int) -> Optional[asyncio.Server]:
        """Create a temporary TCP listener for port verification."""
        try:
            # First check if port is already in use
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                logger.debug(f"Port {port} is already in use - this is expected if our server is running")
                return None
            
            try:
                server = await asyncio.start_server(
                    lambda r, w: None,  # Empty callback since we just need to listen
                    '0.0.0.0', 
                    port
                )
                logger.debug(f"Created temporary listener on port {port}")
                return server
            except PermissionError:
                logger.error(f"Permission denied when trying to bind to port {port}")
                return None
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    logger.debug(f"Port {port} is already in use - this is expected if our server is running")
                    return None
                logger.error(f"Failed to create listener on port {port}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error creating listener on port {port}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to check port {port} status: {e}")
            return None

    async def verify_ports(self, ports: List[int]) -> Dict[int, PortVerificationResult]:
        """Verify ports both locally and externally.
        
        Args:
            ports: List of ports to verify
            
        Returns:
            Dictionary mapping ports to their verification results
        """
        # Separate discovery port from other ports
        other_ports = [p for p in ports if p != self.discovery_port]
        discovery_port_included = self.discovery_port in ports
        
        # First verify ports with local binding
        logger.info("Checking local port availability...")
        async for local_available in self.verify_local_binding(ports):
            if not local_available:
                logger.error("No ports available for local binding")
                return {
                    port: PortVerificationResult(
                        port=port,
                        accessible=False,
                        error="Failed to bind locally"
                    )
                    for port in ports
                }
            
            # Verify external access while listeners are active
            logger.info("Starting external port verification...")
            results = await self.verify_external_access(local_available)
            
            # Log detailed results for discovery port
            if discovery_port_included and self.discovery_port in results:
                result = results[self.discovery_port]
                if result.accessible:
                    logger.info(f"Discovery port {self.discovery_port} verified successfully by {result.verified_by}")
                else:
                    logger.error(f"Discovery port {self.discovery_port} verification failed: {result.error}")
            
            return results
