import asyncio
import logging
from typing import Dict, List, Callable, Optional
from ..vm.models import VMResources
from ..config import settings

logger = logging.getLogger(__name__)

class ResourceTracker:
    """Track and manage provider resources."""

    def __init__(self):
        """Initialize resource tracker."""
        from .resource_monitor import ResourceMonitor
        self.total_resources = {
            "cpu": ResourceMonitor.get_cpu_count(),
            "memory": ResourceMonitor.get_memory_gb(),
            "storage": ResourceMonitor.get_storage_gb()
        }
        self.allocated_resources = {
            "cpu": 0,
            "memory": 0,
            "storage": 0
        }
        self._lock = asyncio.Lock()
        self._update_callbacks: List[Callable] = []
        self._allocated_vms: Dict[str, VMResources] = {}

    def _can_allocate(self, resources: VMResources) -> bool:
        """Check if resources can be allocated."""
        available = self.get_available_resources()
        return (
            resources.cpu <= available["cpu"] and
            resources.memory <= available["memory"] and
            resources.storage <= available["storage"]
        )

    def _meets_minimum_requirements(self, resources: Dict[str, int]) -> bool:
        """Check if available resources meet minimum requirements."""
        return (
            resources["cpu"] >= settings.MIN_CPU_CORES and
            resources["memory"] >= settings.MIN_MEMORY_GB and
            resources["storage"] >= settings.MIN_STORAGE_GB
        )

    async def allocate(self, resources: VMResources, vm_id: Optional[str] = None) -> bool:
        """Allocate resources for a VM."""
        async with self._lock:
            if not self._can_allocate(resources):
                return False
            
            self.allocated_resources["cpu"] += resources.cpu
            self.allocated_resources["memory"] += resources.memory
            self.allocated_resources["storage"] += resources.storage
            
            if vm_id:
                self._allocated_vms[vm_id] = resources
            
            logger.info(
                f"Allocated resources: CPU={resources.cpu}, "
                f"Memory={resources.memory}GB, Storage={resources.storage}GB"
            )
            
            await self._notify_update()
            return True

    async def deallocate(self, resources: VMResources, vm_id: Optional[str] = None) -> None:
        """Deallocate resources from a VM."""
        async with self._lock:
            self.allocated_resources["cpu"] = max(
                0, self.allocated_resources["cpu"] - resources.cpu
            )
            self.allocated_resources["memory"] = max(
                0, self.allocated_resources["memory"] - resources.memory
            )
            self.allocated_resources["storage"] = max(
                0, self.allocated_resources["storage"] - resources.storage
            )
            
            if vm_id and vm_id in self._allocated_vms:
                del self._allocated_vms[vm_id]
            
            logger.info(
                f"Deallocated resources: CPU={resources.cpu}, "
                f"Memory={resources.memory}GB, Storage={resources.storage}GB"
            )
            
            await self._notify_update()

    def get_allocated_vms(self) -> List[str]:
        """Get list of allocated VM IDs."""
        return list(self._allocated_vms.keys())

    def get_available_resources(self) -> Dict[str, int]:
        """Get currently available resources."""
        return {
            "cpu": max(0, self.total_resources["cpu"] - self.allocated_resources["cpu"]),
            "memory": max(0, self.total_resources["memory"] - self.allocated_resources["memory"]),
            "storage": max(0, self.total_resources["storage"] - self.allocated_resources["storage"])
        }

    def can_accept_resources(self, resources: VMResources) -> bool:
        """Check if resources can be accepted."""
        available = self.get_available_resources()
        return (
            resources.cpu <= available["cpu"] and
            resources.memory <= available["memory"] and
            resources.storage <= available["storage"] and
            self._meets_minimum_requirements(available)
        )

    def on_update(self, callback: Callable) -> None:
        """Register callback for resource updates."""
        self._update_callbacks.append(callback)

    async def _notify_update(self) -> None:
        """Notify all registered callbacks of resource update."""
        for callback in self._update_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in resource update callback: {e}")

    async def sync_with_multipass(self, vm_resources: Dict[str, VMResources]) -> None:
        """Sync resource tracker state with actual multipass VM states.
        
        Args:
            vm_resources: Dictionary mapping VM names to their resources
        """
        async with self._lock:
            # Reset allocated resources
            self.allocated_resources = {
                "cpu": 0,
                "memory": 0,
                "storage": 0
            }
            self._allocated_vms.clear()
            
            # Add resources for each running VM
            for vm_name, resources in vm_resources.items():
                self.allocated_resources["cpu"] += resources.cpu
                self.allocated_resources["memory"] += resources.memory
                self.allocated_resources["storage"] += resources.storage
                self._allocated_vms[vm_name] = resources
                
            logger.info(
                f"Synced allocated resources: CPU={self.allocated_resources['cpu']}, "
                f"Memory={self.allocated_resources['memory']}GB, "
                f"Storage={self.allocated_resources['storage']}GB"
            )
            
            await self._notify_update()
