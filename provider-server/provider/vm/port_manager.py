import os
import json
import logging
from pathlib import Path
from typing import Optional, Set
from threading import Lock

logger = logging.getLogger(__name__)

class PortManager:
    """Manages port allocation for VM SSH proxying."""
    
    def __init__(
        self,
        start_port: int = 50800,
        end_port: int = 50900,
        state_file: Optional[str] = None
    ):
        """Initialize the port manager.
        
        Args:
            start_port: Beginning of port range
            end_port: End of port range (exclusive)
            state_file: Path to persist port assignments
        """
        self.start_port = start_port
        self.end_port = end_port
        self.state_file = state_file or os.path.expanduser("~/.golem/provider/ports.json")
        self.lock = Lock()
        self._used_ports: dict[str, int] = {}  # vm_id -> port
        self._load_state()
    
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
        """Allocate a port for a VM.
        
        Args:
            vm_id: Unique identifier for the VM
            
        Returns:
            Allocated port number or None if allocation failed
        """
        with self.lock:
            # Check if VM already has a port
            if vm_id in self._used_ports:
                return self._used_ports[vm_id]
            
            used_ports = self._get_used_ports()
            
            # Find first available port
            for port in range(self.start_port, self.end_port):
                if port not in used_ports:
                    self._used_ports[vm_id] = port
                    self._save_state()
                    logger.info(f"Allocated port {port} for VM {vm_id}")
                    return port
            
            logger.error(f"No available ports in range {self.start_port}-{self.end_port}")
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
