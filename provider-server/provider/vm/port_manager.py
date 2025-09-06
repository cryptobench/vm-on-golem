import os
import json
import socket
import logging
import asyncio
from pathlib import Path
from typing import Optional, Set, List, Dict
from threading import Lock

from ..config import settings
from ..network.port_verifier import PortVerifier, PortVerificationResult, ServerAttempt
from ..utils.port_display import PortVerificationDisplay

logger = logging.getLogger(__name__)


class PortManager:
    """Manages port allocation and verification for VM SSH proxying."""

    def __init__(
        self,
        start_port: int = 50800,
        end_port: int = 50900,
        state_file: Optional[str] = None,
        port_check_servers: Optional[List[str]] = None,
        discovery_port: Optional[int] = None,
        existing_ports: Optional[Set[int]] = None,
        skip_verification: bool = False
    ):
        """Initialize the port manager.

        Args:
            start_port: Beginning of port range
            end_port: End of port range (exclusive)
            state_file: Path to persist port assignments
            port_check_servers: List of URLs for port checking services
            discovery_port: Port used for discovery service
            existing_ports: Set of ports that should be considered in use
        """
        self.start_port = start_port
        self.end_port = end_port
        self.state_file = state_file or os.path.expanduser(
            "~/.golem/provider/ports.json")
        self.lock = Lock()
        self._used_ports: dict[str, int] = {}  # vm_id -> port
        self.verified_ports: Set[int] = set()
        self._existing_ports = existing_ports or set()

        # Initialize port verifier with default servers
        if settings.DEV_MODE:
            self.port_check_servers = ["http://localhost:9000"]
        else:
            self.port_check_servers = port_check_servers or [
                "http://localhost:9000",  # Local development server
                "http://195.201.39.101:9000",  # Production servers
            ]
        self.discovery_port = discovery_port or settings.PORT
        self.skip_verification = skip_verification
        self.port_verifier = PortVerifier(
            self.port_check_servers,
            discovery_port=self.discovery_port
        )

        # Load state after setting existing ports
        self._load_state()
        
        # Mark existing ports as used and remove from verified ports
        for port in self._existing_ports:
            if port in self.verified_ports:
                self.verified_ports.remove(port)
                logger.debug(f"Marked port {port} as in use from existing ports")

    async def initialize(self) -> bool:
        """Initialize port manager with verification.

        Returns:
            bool: True if required ports were verified successfully
        """
        from ..config import settings

        display = PortVerificationDisplay(
            provider_port=self.discovery_port,
            port_range_start=self.start_port,
            port_range_end=self.end_port,
            skip_verification=self.skip_verification
        )
        display.print_header()

        # If verification is skipped, mark all ports as verified
        if self.skip_verification:
            logger.warning("⚠️  Port verification is disabled in development mode")
            logger.warning("   All ports will be considered available")
            logger.warning("   This should only be used for development/testing")
            
            # Mark all ports as verified
            self.verified_ports = set(range(self.start_port, self.end_port))
            
            # In development mode, we don't need to create any results
            # The display will handle development mode differently
            results = {}
        else:
            # Verify all ports in range, including existing ones
            ssh_ports = list(range(self.start_port, self.end_port))
            logger.info(f"Starting port verification...")
            logger.info(f"SSH ports range: {self.start_port}-{self.end_port}")
            logger.info(
                f"Using port check servers: {', '.join(self.port_check_servers)}")

            # Clear existing verified ports before verification
            self.verified_ports.clear()
            results = {}
            if not self.skip_verification:
                try:
                    results = await self.port_verifier.verify_ports(ssh_ports)
                except RuntimeError as e:
                    logger.error(f"Port verification failed: {e}")
                    display.print_summary(
                        PortVerificationResult(
                            port=self.discovery_port,
                            accessible=False,
                            error=str(e)
                        ),
                        {}
                    )
                    return False

        # Add provider port as verified since we already checked it
        results[self.discovery_port] = PortVerificationResult(
            port=self.discovery_port,
            accessible=True,
            verified_by="local_verification",
            attempts=[ServerAttempt(server="local_verification", success=True)]
        )

        # Check if discovery port was verified
        if self.discovery_port not in results:
            error_msg = f"Port {self.discovery_port} verification failed"
            logger.error(error_msg)
            display.print_summary(
                PortVerificationResult(
                    port=self.discovery_port,
                    accessible=False,
                    error=error_msg
                ),
                {}
            )
            return False

        # Display discovery port status with animation
        discovery_result = results[self.discovery_port]
        await display.print_discovery_status(discovery_result)

        if not discovery_result.accessible:
            error_msg = discovery_result.error or f"Port {self.discovery_port} is not accessible"
            logger.error(f"Failed to verify discovery port: {error_msg}")
            # Print summary before returning
            display.print_summary(discovery_result, {})
            return False

        # Display SSH ports status with animation
        ssh_results = {port: result for port,
                       result in results.items() if port != self.discovery_port}
        await display.print_ssh_status(ssh_results)

        # Store verified ports
        self.verified_ports = {
            port for port, result in ssh_results.items() if result.accessible}

        # Only show critical issues and quick fix if there are problems
        if not discovery_result.accessible or not self.verified_ports:
            display.print_critical_issues(discovery_result, ssh_results)
            display.print_quick_fix(discovery_result, ssh_results)

        # Print precise summary of current status
        display.print_summary(discovery_result, ssh_results)

        if self.skip_verification:
            logger.info(f"Port verification skipped - all {len(self.verified_ports)} ports marked as available")
            return True
        else:
            if not self.verified_ports:
                logger.error("No SSH ports were verified as accessible")
                return False

            logger.info(
                f"Successfully verified {len(self.verified_ports)} SSH ports")
            return True

    def _load_state(self) -> None:
        """Load port assignments from state file."""
        try:
            state_path = Path(self.state_file)
            if state_path.exists():
                with open(state_path, 'r') as f:
                    self._used_ports = json.load(f)
                logger.info(
                    f"Loaded port assignments for {len(self._used_ports)} VMs")
            else:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                self._save_state()
        except Exception as e:
            logger.error(f"Failed to load port state: {e}")
            self._used_ports = {}

    def _save_state(self) -> None:
        """Save current port assignments to state file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self._used_ports, f)
        except Exception as e:
            logger.error(f"Failed to save port state: {e}")

    def _get_used_ports(self) -> Set[int]:
        """Get set of currently used ports."""
        return set(self._used_ports.values())

    def allocate_port(self, vm_id: str) -> Optional[int]:
        """Allocate a verified port for a VM.

        Args:
            vm_id: Unique identifier for the VM

        Returns:
            Allocated port number or None if allocation failed
        """
        with self.lock:
            # Check if VM already has a port
            if vm_id in self._used_ports:
                port = self._used_ports[vm_id]
                if port in self.verified_ports:
                    # Quick check if port is still available
                    try:
                        sock = socket.socket(
                            socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('127.0.0.1', port))
                        sock.close()

                        if result != 0:  # Port is available
                            return port
                        else:
                            # Port is in use, remove from verified ports
                            if not self.skip_verification:
                                self.verified_ports.remove(port)
                            self._used_ports.pop(vm_id)
                    except Exception as e:
                        logger.debug(f"Failed to check port {port}: {e}")
                        # Keep the port if check fails, let proxy setup handle any issues
                        return port
                else:
                    # Previously allocated port is no longer verified
                    self._used_ports.pop(vm_id)

            used_ports = self._get_used_ports()

            # Find first available verified port
            ports_to_check = sorted(list(self.verified_ports)) if not self.skip_verification else range(
                self.start_port, self.end_port)
            for port in ports_to_check:
                if port not in used_ports:
                    # Quick check if port is actually available
                    try:
                        sock = socket.socket(
                            socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('127.0.0.1', port))
                        sock.close()

                        if result != 0:  # Port is available
                            self._used_ports[vm_id] = port
                            self._save_state()
                            logger.info(
                                f"Allocated port {port} for VM {vm_id}")
                            return port
                        else:
                            # Port is in use, remove from verified ports
                            if not self.skip_verification and port in self.verified_ports:
                                self.verified_ports.remove(port)
                    except Exception as e:
                        logger.debug(f"Failed to check port {port}: {e}")
                        continue

            logger.error("No verified ports available for allocation")
            return None

    def deallocate_port(self, vm_id: str) -> None:
        """Release a port allocation for a VM.

        Args:
            vm_id: Unique identifier for the VM
        """
        with self.lock:
            if vm_id in self._used_ports:
                port = self._used_ports.pop(vm_id)
                self._save_state()
                logger.info(f"Deallocated port {port} for VM {vm_id}")

    def get_port(self, vm_id: str) -> Optional[int]:
        """Get currently allocated port for a VM.

        Args:
            vm_id: Unique identifier for the VM

        Returns:
            Port number or None if VM has no allocation
        """
        return self._used_ports.get(vm_id)

    def cleanup(self) -> None:
        """Remove all port allocations."""
        with self.lock:
            self._used_ports.clear()
            self._save_state()
            logger.info("Cleared all port allocations")
