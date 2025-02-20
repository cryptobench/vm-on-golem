import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict
from asyncio import Task, Transport, Protocol

from .port_manager import PortManager

logger = logging.getLogger(__name__)

class SSHProxyProtocol(Protocol):
    """Protocol for handling SSH proxy connections."""
    
    def __init__(self, target_host: str, target_port: int):
        self.target_host = target_host
        self.target_port = target_port
        self.transport: Optional[Transport] = None
        self.target_transport: Optional[Transport] = None
        self.target_protocol: Optional['SSHTargetProtocol'] = None
        self.buffer = bytearray()
    
    def connection_made(self, transport: Transport) -> None:
        """Called when connection is established."""
        self.transport = transport
        asyncio.create_task(self.connect_to_target())
    
    async def connect_to_target(self) -> None:
        """Establish connection to target."""
        try:
            loop = asyncio.get_running_loop()
            self.target_protocol = SSHTargetProtocol(self)
            target_transport, _ = await loop.create_connection(
                lambda: self.target_protocol,
                self.target_host,
                self.target_port
            )
            self.target_transport = target_transport
            # If we have buffered data, send it now
            if self.buffer:
                self.target_transport.write(self.buffer)
                self.buffer.clear()
        except Exception as e:
            logger.error(f"Failed to connect to target {self.target_host}:{self.target_port}: {e}")
            if self.transport:
                self.transport.close()
    
    def data_received(self, data: bytes) -> None:
        """Forward received data to target."""
        if self.target_transport and not self.target_transport.is_closing():
            self.target_transport.write(data)
        else:
            # Buffer data until target connection is established
            self.buffer.extend(data)
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection loss."""
        if exc:
            logger.error(f"Client connection lost with error: {exc}")
        if self.target_transport and not self.target_transport.is_closing():
            self.target_transport.close()

class SSHTargetProtocol(Protocol):
    """Protocol for handling target SSH connections."""
    
    def __init__(self, client_protocol: SSHProxyProtocol):
        self.client_protocol = client_protocol
        self.transport: Optional[Transport] = None
    
    def connection_made(self, transport: Transport) -> None:
        """Called when connection is established."""
        self.transport = transport
    
    def data_received(self, data: bytes) -> None:
        """Forward received data to client."""
        if (self.client_protocol.transport and 
            not self.client_protocol.transport.is_closing()):
            self.client_protocol.transport.write(data)
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection loss."""
        if exc:
            logger.error(f"Target connection lost with error: {exc}")
        if (self.client_protocol.transport and 
            not self.client_protocol.transport.is_closing()):
            self.client_protocol.transport.close()

class ProxyServer:
    """Manages a single proxy server instance."""
    
    def __init__(self, listen_port: int, target_host: str, target_port: int = 22):
        """Initialize proxy server.
        
        Args:
            listen_port: Port to listen on
            target_host: Target host to forward to
            target_port: Target port (default: 22 for SSH)
        """
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.server: Optional[asyncio.AbstractServer] = None
    
    async def start(self) -> None:
        """Start the proxy server."""
        loop = asyncio.get_running_loop()
        
        try:
            self.server = await loop.create_server(
                lambda: SSHProxyProtocol(self.target_host, self.target_port),
                '0.0.0.0',  # Listen on all interfaces
                self.listen_port
            )
            logger.info(f"Proxy server listening on port {self.listen_port}")
        except Exception as e:
            logger.error(f"Failed to start proxy server on port {self.listen_port}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the proxy server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info(f"Proxy server on port {self.listen_port} stopped")

class PythonProxyManager:
    """Manages proxy servers for VM SSH access."""
    
    def __init__(
        self,
        port_manager: Optional[PortManager] = None,
        state_file: Optional[str] = None
    ):
        """Initialize the proxy manager.
        
        Args:
            port_manager: Port allocation manager
            state_file: Path to persist proxy state
        """
        self.port_manager = port_manager or PortManager()
        self.state_file = state_file or os.path.expanduser("~/.golem/provider/proxy_state.json")
        self._proxies: Dict[str, ProxyServer] = {}  # vm_id -> ProxyServer
        self._load_state()
    
    def _load_state(self) -> None:
        """Load proxy state from file."""
        try:
            state_path = Path(self.state_file)
            if state_path.exists():
                with open(state_path, 'r') as f:
                    state = json.load(f)
                    # We only need to restore port allocations
                    # Actual proxy servers will be recreated as needed
                    logger.info(f"Loaded proxy state for {len(state)} VMs")
        except Exception as e:
            logger.error(f"Failed to load proxy state: {e}")
    
    def _save_state(self) -> None:
        """Save current proxy state to file."""
        try:
            state = {
                vm_id: {
                    'port': proxy.listen_port,
                    'target': proxy.target_host
                }
                for vm_id, proxy in self._proxies.items()
            }
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save proxy state: {e}")
    
    async def add_vm(self, vm_id: str, vm_ip: str, port: Optional[int] = None) -> bool:
        """Add proxy configuration for a new VM.
        
        Args:
            vm_id: Unique identifier for the VM
            vm_ip: IP address of the VM
            port: Optional specific port to use, if not provided one will be allocated
            
        Returns:
            True if proxy configuration was successful, False otherwise
        """
        try:
            # Use provided port or allocate one
            if port is None:
                port = self.port_manager.allocate_port(vm_id)
                if port is None:
                    logger.error(f"Failed to allocate port for VM {vm_id}")
                    return False
            
            # Create and start proxy server
            proxy = ProxyServer(port, vm_ip)
            await proxy.start()
            
            self._proxies[vm_id] = proxy
            self._save_state()
            
            logger.info(f"Started proxy for VM {vm_id} on port {port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure proxy for VM {vm_id}: {e}")
            # Only deallocate if we allocated the port ourselves
            if port is None and 'port' in locals():
                self.port_manager.deallocate_port(vm_id)
            return False
    
    async def remove_vm(self, vm_id: str) -> None:
        """Remove proxy configuration for a VM.
        
        Args:
            vm_id: Unique identifier for the VM
        """
        try:
            if vm_id in self._proxies:
                proxy = self._proxies.pop(vm_id)
                await proxy.stop()
                self.port_manager.deallocate_port(vm_id)
                self._save_state()
                logger.info(f"Removed proxy for VM {vm_id}")
        except Exception as e:
            logger.error(f"Failed to remove proxy for VM {vm_id}: {e}")
    
    def get_port(self, vm_id: str) -> Optional[int]:
        """Get allocated port for a VM."""
        return self.port_manager.get_port(vm_id)
    
    async def cleanup(self) -> None:
        """Remove all proxy configurations."""
        try:
            for vm_id in list(self._proxies.keys()):
                await self.remove_vm(vm_id)
            self._save_state()
            logger.info("Cleaned up all proxy configurations")
        except Exception as e:
            logger.error(f"Failed to cleanup proxy configurations: {e}")
