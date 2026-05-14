import asyncio
import json
import logging
import os
from asyncio import Protocol, Task, Transport
from pathlib import Path
from typing import Dict, Optional, Set

from .port_manager import PortManager

logger = logging.getLogger(__name__)


class SSHProxyProtocol(Protocol):
    """Protocol for handling SSH proxy connections."""

    def __init__(self, target_host: str, target_port: int, counters: dict):
        self.target_host = target_host
        self.target_port = target_port
        self.counters = counters
        self.transport: Optional[Transport] = None
        self.target_transport: Optional[Transport] = None
        self.target_protocol: Optional["SSHTargetProtocol"] = None
        self.buffer = bytearray()

    def connection_made(self, transport: Transport) -> None:
        """Called when connection is established."""
        self.transport = transport
        self.counters["connections"] = self.counters.get("connections", 0) + 1
        logger.debug(
            "SSH proxy client connected",
            extra={"target_host": self.target_host, "target_port": self.target_port},
        )
        asyncio.create_task(self.connect_to_target())

    async def connect_to_target(self) -> None:
        """Establish connection to target."""
        try:
            loop = asyncio.get_running_loop()
            self.target_protocol = SSHTargetProtocol(self)
            target_transport, _ = await loop.create_connection(
                lambda: self.target_protocol, self.target_host, self.target_port
            )
            self.target_transport = target_transport
            # If we have buffered data, send it now
            if self.buffer:
                self.target_transport.write(self.buffer)
                self.buffer.clear()
        except Exception as e:
            logger.error(
                f"Failed to connect to target {self.target_host}:{self.target_port}: {e}"
            )
            if self.transport:
                self.transport.close()

    def data_received(self, data: bytes) -> None:
        """Forward received data to target."""
        self.counters["tx_bytes"] = self.counters.get("tx_bytes", 0) + len(data)
        if self.target_transport and not self.target_transport.is_closing():
            self.target_transport.write(data)
        else:
            # Buffer data until target connection is established
            self.buffer.extend(data)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection loss."""
        if exc:
            logger.warning(f"Client connection lost with error: {exc}")
        else:
            logger.debug("SSH proxy client disconnected")

        # Ensure target connection is properly closed
        if self.target_transport:
            if not self.target_transport.is_closing():
                self.target_transport.close()
            self.target_transport = None

        # Clear any buffered data
        if self.buffer:
            self.buffer.clear()


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
        self.client_protocol.counters["rx_bytes"] = self.client_protocol.counters.get(
            "rx_bytes", 0
        ) + len(data)
        if (
            self.client_protocol.transport
            and not self.client_protocol.transport.is_closing()
        ):
            self.client_protocol.transport.write(data)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection loss."""
        if exc:
            logger.warning(f"Target connection lost with error: {exc}")
        else:
            logger.debug("SSH proxy target disconnected")

        # Ensure client connection is properly closed
        if self.client_protocol and self.client_protocol.transport:
            if not self.client_protocol.transport.is_closing():
                self.client_protocol.transport.close()
            self.client_protocol.transport = None


class ProxyServer:
    """Manages a single proxy server instance."""

    def __init__(
        self,
        listen_port: int,
        target_host: str,
        target_port: int = 22,
        counters: Optional[dict] = None,
    ):
        """Initialize proxy server.

        Args:
            listen_port: Port to listen on
            target_host: Target host to forward to
            target_port: Target port (default: 22 for SSH)
        """
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.counters = counters if counters is not None else {}
        self.server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        """Start the proxy server."""
        loop = asyncio.get_running_loop()

        try:
            self.server = await loop.create_server(
                lambda: SSHProxyProtocol(
                    self.target_host, self.target_port, self.counters
                ),
                "0.0.0.0",  # Listen on all interfaces
                self.listen_port,
            )
            logger.info(f"Proxy server listening on port {self.listen_port}")
        except Exception as e:
            logger.error(
                f"Failed to start proxy server on port {self.listen_port}: {e}"
            )
            raise

    async def stop(self) -> None:
        """Stop the proxy server."""
        if self.server:
            try:
                # Close the server
                self.server.close()
                await self.server.wait_closed()
                logger.info(f"Proxy server on port {self.listen_port} stopped")
            except Exception as e:
                logger.error(
                    f"Error stopping proxy server on port {self.listen_port}: {e}"
                )
            finally:
                self.server = None


class PythonProxyManager:
    """Manages proxy servers for VM SSH access."""

    def __init__(
        self,
        port_manager: Optional[PortManager],
        name_mapper: "VMNameMapper",
        state_file: Optional[str] = None,
    ):
        """Initialize the proxy manager.

        Args:
            port_manager: Port allocation manager (optional during startup)
            name_mapper: VM name mapping manager
            state_file: Path to persist proxy state
        """
        self.port_manager = port_manager
        self.name_mapper = name_mapper
        self.state_file = state_file or os.path.expanduser(
            "~/.golem/provider/proxy_state.json"
        )
        self._proxies: Dict[str, ProxyServer] = {}  # multipass_name -> ProxyServer
        self._state_version = 1  # For future state schema migrations
        self._active_ports: Dict[str, int] = {}  # multipass_name -> port
        self._traffic_counters: Dict[str, dict] = {}

    async def initialize(self) -> None:
        """Restore persisted proxy listeners."""
        await self._load_state()

    def get_active_ports(self) -> Set[int]:
        """Get set of ports that should be considered in use.

        Returns:
            Set of ports that are allocated to VMs
        """
        return set(self._active_ports.values())

    async def _load_state(self) -> None:
        """Load and restore proxy state from file."""
        try:
            state_path = Path(self.state_file)
            if not state_path.exists():
                logger.info(f"No persisted proxy state found at {state_path}")
                return

            with open(state_path, "r") as f:
                state = json.load(f)

            persisted_proxies = state.get("proxies", {})
            logger.info(
                f"Loaded {len(persisted_proxies)} persisted proxy definitions "
                f"from {state_path}"
            )

            # Check state version for future migrations
            if state.get("version", 1) != self._state_version:
                logger.warning(
                    f"State version mismatch: {state.get('version')} != {self._state_version}"
                )

            # First load all port allocations
            for requestor_name, proxy_info in persisted_proxies.items():
                multipass_name = await self.name_mapper.get_multipass_name(
                    requestor_name
                )
                if multipass_name:
                    self._active_ports[multipass_name] = proxy_info["port"]

            # Then attempt to restore proxies with retries
            restore_tasks = []
            for requestor_name, proxy_info in persisted_proxies.items():
                multipass_name = await self.name_mapper.get_multipass_name(
                    requestor_name
                )
                if multipass_name:
                    logger.info(
                        "Restoring persisted SSH proxy "
                        f"requestor_vm={requestor_name} "
                        f"multipass={multipass_name} "
                        f"listen_port={proxy_info['port']} "
                        f"target={proxy_info['target']}:22"
                    )
                    task = self._restore_proxy_with_retry(
                        multipass_name=multipass_name,
                        vm_ip=proxy_info["target"],
                        port=proxy_info["port"],
                    )
                    restore_tasks.append(task)
                else:
                    logger.warning(
                        f"No multipass name found for requestor VM {requestor_name}"
                    )

            # Wait for all restore attempts
            if restore_tasks:
                results = await asyncio.gather(*restore_tasks, return_exceptions=True)
                successful = sum(1 for r in results if r is True)
                logger.info(
                    f"Restored {successful}/{len(persisted_proxies)} proxy configurations"
                )

        except Exception as e:
            logger.error(f"Failed to load proxy state: {e}")

    async def _restore_proxy_with_retry(
        self,
        multipass_name: str,
        vm_ip: str,
        port: int,
        max_retries: int = 3,
        initial_delay: float = 1.0,
    ) -> bool:
        """Attempt to restore a proxy with exponential backoff retry.

        Args:
            multipass_name: Multipass VM name
            vm_ip: VM IP address
            port: Port to use
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries (doubles each attempt)

        Returns:
            bool: True if restoration was successful
        """
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt + 1} for {multipass_name} on port {port}"
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff

                # Check if port is verified before restoring
                if (
                    not self.port_manager
                    or port not in self.port_manager.verified_ports
                ):
                    logger.warning(
                        f"Port {port} is not verified, skipping proxy restoration for {multipass_name}"
                    )
                    # Remove from active ports since we can't restore it
                    self._active_ports.pop(multipass_name, None)
                    return False

                # Attempt to create proxy
                counters = self._traffic_counters.setdefault(
                    multipass_name, {"rx_bytes": 0, "tx_bytes": 0, "connections": 0}
                )
                proxy = ProxyServer(port, vm_ip, counters=counters)
                await proxy.start()

                self._proxies[multipass_name] = proxy
                self._active_ports[multipass_name] = port
                logger.info(
                    f"Successfully restored proxy for {multipass_name} on port {port}"
                )
                return True

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed for {multipass_name}: {e}"
                )
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to restore proxy for {multipass_name} after {max_retries} attempts"
                    )
                    # Remove from active ports if all retries failed
                    self._active_ports.pop(multipass_name, None)
                    return False

    async def _save_state(self) -> None:
        """Save current proxy state to file using requestor names."""
        try:
            state = {"version": self._state_version, "proxies": {}}

            for multipass_name, proxy in self._proxies.items():
                requestor_name = await self.name_mapper.get_requestor_name(
                    multipass_name
                )
                if requestor_name:
                    state["proxies"][requestor_name] = {
                        "port": proxy.listen_port,
                        "target": proxy.target_host,
                    }

            # Save to temporary file first
            temp_file = f"{self.state_file}.tmp"
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            with open(temp_file, "w") as f:
                json.dump(state, f, indent=2)

            # Atomic rename
            os.replace(temp_file, self.state_file)

        except Exception as e:
            logger.error(f"Failed to save proxy state: {e}")

    async def add_vm(self, vm_id: str, vm_ip: str, port: Optional[int] = None) -> bool:
        """Add proxy configuration for a new VM.

        Args:
            vm_id: Unique identifier for the VM (multipass name)
            vm_ip: IP address of the VM
            port: Optional specific port to use, if not provided one will be allocated

        Returns:
            True if proxy configuration was successful, False otherwise
        """
        try:
            # Use provided port or allocate one
            if port is None:
                allocated_port = self.port_manager.allocate_port(vm_id)
                if allocated_port is None:
                    logger.error(f"Failed to allocate port for VM {vm_id}")
                    return False
                port = allocated_port
                logger.info(
                    "Allocated SSH proxy port",
                    extra={"vm_id": vm_id, "port": port},
                )

            # Create and start proxy server
            counters = self._traffic_counters.setdefault(
                vm_id, {"rx_bytes": 0, "tx_bytes": 0, "connections": 0}
            )
            proxy = ProxyServer(port, vm_ip, counters=counters)
            await proxy.start()

            self._proxies[vm_id] = proxy
            self._active_ports[vm_id] = port
            await self._save_state()

            logger.info(f"Started proxy for VM {vm_id} on port {port}")
            return True

        except Exception as e:
            logger.error(f"Failed to configure proxy for VM {vm_id}: {e}")
            # Only deallocate if we allocated the port ourselves
            if "allocated_port" in locals() and allocated_port:
                self.port_manager.deallocate_port(vm_id)
            return False

    async def remove_vm(self, vm_id: str) -> None:
        """Remove proxy configuration for a VM.

        Args:
            vm_id: Unique identifier for the VM (multipass name)
        """
        try:
            proxy = self._proxies.pop(vm_id, None)
            if proxy is not None:
                await proxy.stop()
            if vm_id in self._active_ports:
                self._active_ports.pop(vm_id, None)
            if self.port_manager:
                self.port_manager.deallocate_port(vm_id)
                logger.info("Released SSH proxy port", extra={"vm_id": vm_id})
            self._traffic_counters.pop(vm_id, None)
            await self._save_state()
            logger.info(f"Removed proxy for VM {vm_id}")
        except Exception as e:
            logger.error(f"Failed to remove proxy for VM {vm_id}: {e}")

    def get_port(self, vm_id: str) -> Optional[int]:
        """Get the listening proxy port for a VM."""
        proxy = self._proxies.get(vm_id)
        if proxy is None or proxy.server is None:
            return None
        return proxy.listen_port

    def get_traffic_counters(self) -> Dict[str, dict]:
        """Return proxy byte counters keyed by both multipass and requestor VM names."""
        counters = {key: dict(value) for key, value in self._traffic_counters.items()}
        try:
            for (
                requestor_name,
                multipass_name,
            ) in self.name_mapper.list_mappings().items():
                if multipass_name in counters:
                    counters[requestor_name] = dict(counters[multipass_name])
        except Exception:
            pass
        return counters

    async def cleanup(self) -> None:
        """Remove all proxy configurations."""
        cleanup_errors = []

        # Stop all proxy servers
        for vm_id in list(self._proxies.keys()):
            try:
                await self.remove_vm(vm_id)
            except Exception as e:
                cleanup_errors.append(f"Failed to remove proxy for VM {vm_id}: {e}")

        try:
            await self._save_state()
        except Exception as e:
            cleanup_errors.append(f"Failed to save state: {e}")

        if cleanup_errors:
            error_msg = "\n".join(cleanup_errors)
            logger.error(f"Errors during proxy cleanup:\n{error_msg}")
        else:
            logger.info("Cleaned up all proxy configurations")

        # Clear internal state
        self._proxies.clear()
