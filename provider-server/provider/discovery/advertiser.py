import aiohttp
import asyncio
import logging
import psutil
from datetime import datetime
from typing import Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """Monitor system resources."""
    
    @staticmethod
    def get_cpu_count() -> int:
        """Get number of CPU cores."""
        return psutil.cpu_count()

    @staticmethod
    def get_memory_gb() -> int:
        """Get available memory in GB."""
        return psutil.virtual_memory().available // (1024 ** 3)

    @staticmethod
    def get_storage_gb() -> int:
        """Get available storage in GB."""
        return psutil.disk_usage("/").free // (1024 ** 3)

    @staticmethod
    def get_cpu_percent() -> float:
        """Get CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    @staticmethod
    def get_memory_percent() -> float:
        """Get memory usage percentage."""
        return psutil.virtual_memory().percent

    @staticmethod
    def get_storage_percent() -> float:
        """Get storage usage percentage."""
        return psutil.disk_usage("/").percent

    @classmethod
    def can_accept_resources(
        cls,
        cpu: int,
        memory: int,
        storage: int
    ) -> bool:
        """Check if system can accept requested resources."""
        # Check CPU cores
        if cpu > cls.get_cpu_count():
            return False

        # Check memory (with threshold)
        available_memory = cls.get_memory_gb()
        if memory > available_memory or cls.get_memory_percent() > settings.MEMORY_THRESHOLD:
            return False

        # Check storage (with threshold)
        available_storage = cls.get_storage_gb()
        if storage > available_storage or cls.get_storage_percent() > settings.STORAGE_THRESHOLD:
            return False

        # Check CPU usage
        if cls.get_cpu_percent() > settings.CPU_THRESHOLD:
            return False

        return True

    @classmethod
    def get_available_resources(cls) -> Dict[str, int]:
        """Get available system resources."""
        return {
            "cpu": cls.get_cpu_count(),
            "memory": cls.get_memory_gb(),
            "storage": cls.get_storage_gb()
        }

class ResourceAdvertiser:
    """Advertise available resources to discovery service."""
    
    def __init__(
        self,
        discovery_url: Optional[str] = None,
        provider_id: Optional[str] = None,
        update_interval: Optional[int] = None
    ):
        self.discovery_url = discovery_url or settings.DISCOVERY_URL
        self.provider_id = provider_id or settings.PROVIDER_ID
        self.update_interval = update_interval or settings.ADVERTISEMENT_INTERVAL
        self.session: Optional[aiohttp.ClientSession] = None
        self.monitor = ResourceMonitor()
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start advertising resources."""
        self.session = aiohttp.ClientSession()
        try:
            while not self._stop_event.is_set():
                try:
                    await self._post_advertisement()
                except Exception as e:
                    logger.error(f"Failed to post advertisement: {e}")
                    # Shorter interval for retries
                    await asyncio.sleep(min(60, self.update_interval))
                else:
                    await asyncio.sleep(self.update_interval)
        finally:
            await self.stop()

    async def stop(self):
        """Stop advertising resources."""
        self._stop_event.set()
        if self.session:
            await self.session.close()
            self.session = None

    async def _post_advertisement(self):
        """Post resource advertisement to discovery service."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        resources = self.monitor.get_available_resources()
        
        # Don't advertise if resources are too low
        if not self.monitor.can_accept_resources(
            cpu=settings.MIN_CPU_CORES,
            memory=settings.MIN_MEMORY_GB,
            storage=settings.MIN_STORAGE_GB
        ):
            logger.warning("Resources too low, skipping advertisement")
            return

        async with self.session.post(
            f"{self.discovery_url}/api/v1/advertisements",
            headers={
                "X-Provider-ID": self.provider_id,
                "X-Provider-Signature": "signature",  # TODO: Implement signing
                "Content-Type": "application/json"
            },
            json={
                "ip_address": await self._get_public_ip(),
                "country": settings.COUNTRY,
                "resources": resources
            }
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(
                    f"Failed to post advertisement: {response.status} - {error_text}"
                )
            logger.info(
                f"Posted advertisement with resources: CPU={resources['cpu']}, "
                f"Memory={resources['memory']}GB, Storage={resources['storage']}GB"
            )

    async def _get_public_ip(self) -> str:
        """Get public IP address."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        # Try multiple IP services in case one fails
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://api.my-ip.io/ip"
        ]

        for service in services:
            try:
                async with self.session.get(service) as response:
                    if response.ok:
                        return (await response.text()).strip()
            except Exception as e:
                logger.warning(f"Failed to get IP from {service}: {e}")
                continue

        raise Exception("Failed to get public IP address")
