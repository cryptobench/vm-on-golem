import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import aiohttp

from ..config import settings
from ..utils.retry import async_retry
from .resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)


class DiscoveryPublisher(ABC):
    """Abstract base class for discovery advertisement publishers."""

    @abstractmethod
    async def initialize(self):
        """Initialize the publisher."""
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


class CentralDiscoveryPublisher(DiscoveryPublisher):
    """Publish provider advertisements to the centralized discovery service."""

    def __init__(
        self,
        resource_tracker: "ResourceTracker",
        discovery_url: Optional[str] = None,
        provider_id: Optional[str] = None,
        certificate_service: Any = None,
    ):
        self.resource_tracker = resource_tracker
        self.discovery_url = discovery_url or settings.DISCOVERY_URL
        self.provider_id = provider_id or settings.PROVIDER_ID
        self.certificate_service = certificate_service
        self.session: Optional[aiohttp.ClientSession] = None
        self._stop_event = asyncio.Event()

    async def initialize(self):
        """Initialize the publisher."""
        logger.info("Initializing central discovery publisher")
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        self.resource_tracker.on_update(
            lambda: (
                logger.debug("Resource update triggered central advertisement post"),
                asyncio.create_task(self.post_advertisement()),
            )
        )
        try:
            await self._check_discovery_health()
        except Exception as e:
            logger.warning(
                f"Could not connect to central discovery after retries, continuing without advertising: {e}"
            )
            return
        logger.info("Central discovery publisher initialized")

    async def start_loop(self):
        """Start publishing resource advertisements in a loop."""
        logger.info("Central discovery advertisement loop started")
        try:
            while not self._stop_event.is_set():
                logger.debug("Posting periodic central discovery advertisement")
                await self.post_advertisement()
                await asyncio.sleep(settings.DISCOVERY_ADVERTISEMENT_INTERVAL)
        finally:
            await self.stop()

    async def stop(self):
        """Stop publishing resource advertisements."""
        self._stop_event.set()
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Central discovery publisher stopped")

    @async_retry(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
    )
    async def _check_discovery_health(self):
        """Check central discovery service health with retries."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        async with self.session.get(f"{self.discovery_url}/health") as response:
            if not response.ok:
                raise Exception(
                    f"Central discovery health check failed: {response.status}"
                )

    @async_retry(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
    )
    async def post_advertisement(self):
        """Post resource advertisement to central discovery."""
        if not self.session:
            raise RuntimeError("Session not initialized")

        if not _endpoint_is_advertisable(self.certificate_service):
            logger.warning(
                "Skipping central discovery advertisement because provider "
                "certificate is not usable"
            )
            return

        resources = self.resource_tracker.get_available_resources()
        logger.debug(
            "Prepared central discovery advertisement resources",
            extra={
                "cpu": resources.get("cpu"),
                "memory": resources.get("memory"),
                "storage": resources.get("storage"),
            },
        )

        if not self.resource_tracker._meets_minimum_requirements(resources):
            logger.warning("Resources too low, skipping advertisement")
            return

        ip_address = settings.PUBLIC_IP
        if not ip_address:
            try:
                ip_address = await self._get_public_ip()
            except Exception as e:
                logger.error(f"Could not get public IP after retries: {e}")
                return

        try:
            import platform as _plat

            raw = (_plat.machine() or "").lower()
            platform_str = None
            if raw:
                if "aarch64" in raw or "arm64" in raw or raw.startswith("arm"):
                    platform_str = "arm64"
                elif "x86_64" in raw or "amd64" in raw or "x64" in raw:
                    platform_str = "x86_64"
                else:
                    platform_str = raw
            endpoint_host = ip_address
            endpoint_port = int(getattr(settings, "PUBLIC_HTTPS_PORT", 443))
            endpoint_url = (
                f"https://{endpoint_host}"
                if endpoint_port == 443
                else f"https://{endpoint_host}:{endpoint_port}"
            )
            async with self.session.post(
                f"{self.discovery_url}/api/v1/advertisements",
                headers={
                    "X-Provider-ID": self.provider_id,
                    "X-Provider-Signature": "signature",
                    "Content-Type": "application/json",
                },
                json={
                    "ip_address": ip_address,
                    "country": settings.PROVIDER_COUNTRY,
                    "platform": platform_str,
                    "endpoint_protocol": "https",
                    "endpoint_host": endpoint_host,
                    "endpoint_port": endpoint_port,
                    "endpoint_url": endpoint_url,
                    "resources": resources,
                    "pricing": {
                        "usd_per_core_month": settings.PRICE_USD_PER_CORE_MONTH,
                        "usd_per_gb_ram_month": settings.PRICE_USD_PER_GB_RAM_MONTH,
                        "usd_per_gb_storage_month": settings.PRICE_USD_PER_GB_STORAGE_MONTH,
                        "glm_per_core_month": settings.PRICE_GLM_PER_CORE_MONTH,
                        "glm_per_gb_ram_month": settings.PRICE_GLM_PER_GB_RAM_MONTH,
                        "glm_per_gb_storage_month": settings.PRICE_GLM_PER_GB_STORAGE_MONTH,
                    },
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to post advertisement: {response.status} - {error_text}"
                    )
                logger.info(
                    f"Posted central discovery advertisement with resources: CPU={resources['cpu']}, "
                    f"Memory={resources['memory']}GB, Storage={resources['storage']}GB"
                )
        except asyncio.TimeoutError:
            logger.error("Advertisement request timed out", exc_info=True)
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
            "https://api.my-ip.io/ip",
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

        raise Exception(
            f"Failed to get public IP address from all services: {'; '.join(errors)}"
        )


def _endpoint_is_advertisable(certificate_service: Any) -> bool:
    if certificate_service is None:
        return True
    return bool(certificate_service.endpoint_is_advertisable())
