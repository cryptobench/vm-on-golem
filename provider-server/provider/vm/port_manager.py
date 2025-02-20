import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Set, List, Dict
from threading import Lock

from ..config import settings
from ..network.port_verifier import PortVerifier, PortVerificationResult
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
        discovery_port: Optional[int] = None
    ):
        """Initialize the port manager.
        
        Args:
            start_port: Beginning of port range
            end_port: End of port range (exclusive)
            state_file: Path to persist port assignments
            port_check_servers: List of URLs for port checking services
        """
        self.start_port = start_port
        self.end_port = end_port
        self.state_file = state_file or os.path.expanduser("~/.golem/provider/ports.json")
        self.lock = Lock()
        self._used_ports: dict[str, int] = {}  # vm_id -> port
        self.verified_ports: Set[int] = set()
        
        # Initialize port verifier with default servers
        self.port_check_servers = port_check_servers or [
            # "http://portcheck1.golem.network:7466",
            # "http://portcheck2.golem.network:7466",
            # "http://portcheck3.golem.network:7466",
            "http://localhost:9000"  # Fallback for local development
        ]
        self.discovery_port = discovery_port or settings.PORT
        self.port_verifier = PortVerifier(
            self.port_check_servers,
            discovery_port=self.discovery_port
        )
        
        self._load_state()
    
    async def initialize(self) -> bool:
        """Initialize port manager with verification.
        
        Returns:
            bool: True if required ports were verified successfully
        """
        from ..config import settings
        
        display = PortVerificationDisplay(
            provider_port=self.discovery_port,
            port_range_start=self.start_port,
            port_range_end=self.end_port
        )
        display.print_header()
        
        # Verify all ports together (discovery port and SSH ports)
        all_ports = [self.discovery_port] + list(range(self.start_port, self.end_port))
        logger.info(f"Verifying all ports: discovery port {self.discovery_port} and SSH ports {self.start_port}-{self.end_port}...")
        
        results = await self.port_verifier.verify_ports(all_ports)
        
        # Display discovery port status with animation
        discovery_result = results[self.discovery_port]
        await display.print_discovery_status(discovery_result)
        
        if not discovery_result.accessible:
            logger.error(f"Failed to verify discovery port: {discovery_result.error}")
            # Print summary before returning
            display.print_summary(discovery_result, {})
            return False
            
        # Display SSH ports status with animation
        ssh_results = {port: result for port, result in results.items() if port != self.discovery_port}
        await display.print_ssh_status(ssh_results)
        
        # Store verified ports
        self.verified_ports = {port for port, result in ssh_results.items() if result.accessible}
        
        # Only show critical issues and quick fix if there are problems
        if not discovery_result.accessible or not self.verified_ports:
            display.print_critical_issues(discovery_result, ssh_results)
            display.print_quick_fix(discovery_result, ssh_results)
        
        # Print precise summary of current status
        display.print_summary(discovery_result, ssh_results)
        
        if not self.verified_ports:
            logger.error("No SSH ports were verified as accessible")
            return False
            
        logger.info(f"Successfully verified {len(self.verified_ports)} SSH ports")
        return True
        
    def _load_state(self) -> None:
        """Load port assignments from state file."""
        try:
            state_path = Path(self.state_file)
            if state_path.exists():
                with open(state_path, 'r') as f:
                    self._used_ports = json.load(f)
                logger.info(f"Loaded port assignments for {len(self._used_ports)} VMs")
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
                    return port
                else:
                    # Previously allocated port is no longer verified
                    self._used_ports.pop(vm_id)
            
            used_ports = self._get_used_ports()
            
            # Find first available verified port
            for port in sorted(self.verified_ports):
                if port not in used_ports:
                    self._used_ports[vm_id] = port
                    self._save_state()
                    logger.info(f"Allocated verified port {port} for VM {vm_id}")
                    return port
            
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
