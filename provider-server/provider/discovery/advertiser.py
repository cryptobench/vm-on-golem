import aiohttp
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..config import settings
from ..utils.retry import async_retry
from .resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)

class Advertiser(ABC):
    """Abstract base class for advertisers."""

    @abstractmethod
    async def initialize(self):
        """Initialize the advertiser."""
        pass

    @abstractmethod
    async def start_loop(self):
        """Start the advertising loop."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the advertising loop."""
        pass

    @abstractmethod
    async def post_advertisement(self):
        """Post a single advertisement."""
        pass

class DiscoveryServerAdvertiser(Advertiser):
    """Advertise available resources to a discovery service."""
    
    def __init__(
        self,
        resource_tracker: 'ResourceTracker',
        discovery_url: Optional[str] = None,
        provider_id: Optional[str] = None,
    ):
        self.resource_tracker = resource_tracker
        self.discovery_url = discovery_url or settings.DISCOVERY_URL
        self.provider_id = provider_id or settings.PROVIDER_ID
        self.session: Optional[aiohttp.ClientSession] = None
        self._stop_event = asyncio.Event()

    async def initialize(self):
        """Initialize the advertiser."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        self.resource_tracker.on_update(
            lambda: asyncio.create_task(self.post_advertisement())
        )
        try:
            await self._check_discovery_health()
        except Exception as e:
            logger.warning(f"Could not connect to discovery service after retries, continuing without advertising: {e}")
            return

    async def start_loop(self):
        """Start advertising resources in a loop."""
        try:
            while not self._stop_event.is_set():
                await self.post_advertisement()
                await asyncio.sleep(settings.DISCOVERY_ADVERTISEMENT_INTERVAL)
        finally:
            await self.stop()

    async def stop(self):
        """Stop advertising resources."""
        self._stop_event.set()
        if self.session:
            await self.session.close()
            self.session = None

    @async_retry(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
    )
    async def _check_discovery_health(self):
        """Check discovery service health with retries."""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        async with self.session.get(f"{self.discovery_url}/health") as response:
            if not response.ok:
                raise Exception(f"Discovery service health check failed: {response.status}")

    @async_retry(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
    )
    async def post_advertisement(self):
        """Post resource advertisement to discovery service."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        resources = self.resource_tracker.get_available_resources()
        
        if not self.resource_tracker._meets_minimum_requirements(resources):
            logger.warning("Resources too low, skipping advertisement")
            return

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
                    "X-Provider-Signature": "signature",
                    "Content-Type": "application/json"
                },
                json={
                    "ip_address": ip_address,
                    "country": settings.PROVIDER_COUNTRY,
                    "resources": resources,
                    "pricing": {
                        "usd_per_core_month": settings.PRICE_USD_PER_CORE_MONTH,
                        "usd_per_gb_ram_month": settings.PRICE_USD_PER_GB_RAM_MONTH,
                        "usd_per_gb_storage_month": settings.PRICE_USD_PER_GB_STORAGE_MONTH,
                        "glm_per_core_month": settings.PRICE_GLM_PER_CORE_MONTH,
                        "glm_per_gb_ram_month": settings.PRICE_GLM_PER_GB_RAM_MONTH,
                        "glm_per_gb_storage_month": settings.PRICE_GLM_PER_GB_STORAGE_MONTH,
                    }
                },
                timeout=aiohttp.ClientTimeout(total=5)
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

    @async_retry(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
    )
    async def _get_public_ip(self) -> str:
        """Get public IP address with retries."""
        if not self.session:
            raise RuntimeError("Session not initialized")

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
