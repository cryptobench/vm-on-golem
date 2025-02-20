import aiohttp
import asyncio
import logging
import psutil
from datetime import datetime
from typing import Dict, Optional

from ..config import settings
from ..utils.retry import async_retry

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

class ResourceAdvertiser:
    """Advertise available resources to discovery service."""
    
    def __init__(
        self,
        resource_tracker: 'ResourceTracker',
        discovery_url: Optional[str] = None,
        provider_id: Optional[str] = None,
        update_interval: Optional[int] = None
    ):
        self.resource_tracker = resource_tracker
        self.discovery_url = discovery_url or settings.DISCOVERY_URL
        self.provider_id = provider_id or settings.PROVIDER_ID
        self.update_interval = update_interval or settings.ADVERTISEMENT_INTERVAL
        self.session: Optional[aiohttp.ClientSession] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start advertising resources."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        # Register for resource updates
        self.resource_tracker.on_update(self._post_advertisement)
        
        # Test discovery service connection with retries
        try:
            await self._check_discovery_health()
        except Exception as e:
            logger.warning(f"Could not connect to discovery service after retries, continuing without advertising: {e}")
            return
            
        try:
            while not self._stop_event.is_set():
                try:
                    await self._post_advertisement()
                except aiohttp.ClientError as e:
                    logger.error(f"Network error posting advertisement: {e}")
                    await asyncio.sleep(min(60, self.update_interval))
                except Exception as e:
                    logger.error(f"Failed to post advertisement: {e}")
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

    @async_retry(retries=5, delay=1.0, backoff=2.0, exceptions=(aiohttp.ClientError, asyncio.TimeoutError))
    async def _check_discovery_health(self):
        """Check discovery service health with retries."""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        async with self.session.get(f"{self.discovery_url}/health") as response:
            if not response.ok:
                raise Exception(f"Discovery service health check failed: {response.status}")

    @async_retry(retries=3, delay=1.0, backoff=2.0, exceptions=(aiohttp.ClientError, asyncio.TimeoutError))
    async def _post_advertisement(self):
        """Post resource advertisement to discovery service."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        resources = self.resource_tracker.get_available_resources()
        
        # Don't advertise if resources are too low
        if not self.resource_tracker._meets_minimum_requirements(resources):
            logger.warning("Resources too low, skipping advertisement")
            return

        # Get public IP with retries
        try:
            ip_address = await self._get_public_ip()
        except Exception as e:
            logger.error(f"Could not get public IP after retries: {e}")
            return

        try:
            async with self.session.post(
                f"{self.discovery_url}/api/v1/advertisements",
                headers={
                    "X-Provider-ID": self.provider_id,
                    "X-Provider-Signature": "signature",  # TODO: Implement signing
                    "Content-Type": "application/json"
                },
                json={
                    "ip_address": ip_address,
                    "country": settings.PROVIDER_COUNTRY,
                    "resources": resources
                },
                timeout=aiohttp.ClientTimeout(total=5)  # 5 second timeout for advertisement
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
        except asyncio.TimeoutError:
            logger.error("Advertisement request timed out")
            raise

    @async_retry(retries=3, delay=1.0, backoff=2.0, exceptions=(aiohttp.ClientError, asyncio.TimeoutError))
    async def _get_public_ip(self) -> str:
        """Get public IP address with retries."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        # Try multiple IP services in case one fails
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://api.my-ip.io/ip"
        ]

        errors = []
        for service in services:
            try:
                async with self.session.get(service) as response:
                    if response.ok:
                        return (await response.text()).strip()
            except Exception as e:
                errors.append(f"{service}: {str(e)}")
                continue

        raise Exception(f"Failed to get public IP address from all services: {'; '.join(errors)}")
