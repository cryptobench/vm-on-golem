import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct

from ..config import settings
from ..utils.retry import async_retry
from ..utils.time import utc_now
from .resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)


def provider_auth_message(provider_id: str, nonce: str, timestamp: str) -> str:
    return f"central-discovery-auth:{provider_id}:{nonce}:{timestamp}"


class DiscoveryPublisher(ABC):
    @abstractmethod
    async def initialize(self):
        pass

    @abstractmethod
    async def start_loop(self):
        pass

    @abstractmethod
    async def stop(self):
        pass

    @abstractmethod
    async def post_advertisement(self):
        pass


class CentralDiscoveryPublisher(DiscoveryPublisher):
    """Maintain one live central-discovery provider websocket."""

    def __init__(
        self,
        resource_tracker: ResourceTracker,
        discovery_ws_url: Optional[str] = None,
        provider_id: Optional[str] = None,
        certificate_service: Any = None,
    ):
        self.resource_tracker = resource_tracker
        self.discovery_ws_url = discovery_ws_url or settings.DISCOVERY_WS_URL
        self.provider_id = provider_id or settings.PROVIDER_ID
        self.certificate_service = certificate_service
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._stop_event = asyncio.Event()
        self._publish_lock = asyncio.Lock()

    async def initialize(self):
        logger.info("Initializing central discovery websocket publisher")
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        self.resource_tracker.on_update(
            lambda: asyncio.create_task(self.post_advertisement())
        )
        await self._connect()
        await self.post_advertisement()
        logger.info("Central discovery websocket publisher initialized")

    async def start_loop(self):
        logger.info("Central discovery websocket listener started")
        while not self._stop_event.is_set():
            try:
                if self.websocket is None or self.websocket.closed:
                    await self._connect()
                    await self.post_advertisement()

                async for message in self.websocket:
                    if self._stop_event.is_set():
                        break
                    if message.type == aiohttp.WSMsgType.ERROR:
                        raise RuntimeError(
                            f"central discovery websocket error: {self.websocket.exception()}"
                        )
                    if message.type in {
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                    }:
                        break
            except asyncio.CancelledError:
                raise
            except Exception:
                if self._stop_event.is_set():
                    break
                logger.error("Central discovery websocket disconnected", exc_info=True)
                await self._close_websocket()
                await asyncio.sleep(5)

    async def stop(self):
        self._stop_event.set()
        await self._close_websocket()
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Central discovery websocket publisher stopped")

    async def post_advertisement(self):
        async with self._publish_lock:
            await self._ensure_connected()
            if not _endpoint_is_advertisable(self.certificate_service):
                await self._send_remove()
                return

            resources = self.resource_tracker.get_available_resources()
            if not self.resource_tracker._meets_minimum_requirements(resources):
                await self._send_remove()
                return

            advertisement = await self._advertisement(resources)
            await self.websocket.send_json(
                {"type": "advertisement.upsert", "advertisement": advertisement}
            )
            logger.info(
                "Published central discovery advertisement",
                extra={
                    "provider_id": self.provider_id,
                    "cpu": resources["cpu"],
                    "memory": resources["memory"],
                    "storage": resources["storage"],
                },
            )

    async def _connect(self):
        if not self.session:
            raise RuntimeError("central discovery websocket session not initialized")
        await self._close_websocket()
        websocket = await self.session.ws_connect(self.discovery_ws_url)
        hello = await websocket.receive_json()
        if hello.get("type") != "hello" or not hello.get("nonce"):
            await websocket.close()
            raise RuntimeError("central discovery websocket did not send auth nonce")

        timestamp = utc_now().isoformat()
        await websocket.send_json(
            {
                "type": "authenticate",
                "provider_id": self.provider_id,
                "nonce": hello["nonce"],
                "timestamp": timestamp,
                "signature": self._sign_auth(hello["nonce"], timestamp),
            }
        )
        response = await websocket.receive_json()
        if response.get("type") != "authenticated":
            await websocket.close()
            raise RuntimeError(f"central discovery auth failed: {response}")
        self.websocket = websocket

    async def _ensure_connected(self):
        if self.websocket is None or self.websocket.closed:
            await self._connect()

    async def _close_websocket(self):
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        self.websocket = None

    async def _send_remove(self):
        await self.websocket.send_json({"type": "advertisement.remove"})
        logger.info(
            "Removed central discovery advertisement",
            extra={"provider_id": self.provider_id},
        )

    async def _advertisement(self, resources: dict[str, int]) -> dict[str, Any]:
        ip_address = settings.PUBLIC_IP or await self._get_public_ip()
        platform_str = _platform()
        (
            endpoint_protocol,
            endpoint_host,
            endpoint_port,
            endpoint_url,
        ) = _provider_endpoint(settings, ip_address)
        return {
            "ip_address": ip_address,
            "country": settings.PROVIDER_COUNTRY,
            "platform": platform_str,
            "endpoint_protocol": endpoint_protocol,
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
        }

    def _sign_auth(self, nonce: str, timestamp: str) -> str:
        private_key = settings.ETHEREUM_PRIVATE_KEY
        if not private_key:
            raise RuntimeError("ETHEREUM_PRIVATE_KEY is required for discovery auth")
        signed = Account.sign_message(
            encode_defunct(
                text=provider_auth_message(self.provider_id, nonce, timestamp)
            ),
            private_key=private_key,
        )
        signature = signed.signature.hex()
        return signature if signature.startswith("0x") else f"0x{signature}"

    @async_retry(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
    )
    async def _get_public_ip(self) -> str:
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
            except Exception as exc:
                errors.append(f"{service}: {exc}")

        raise RuntimeError(
            f"failed to get public IP address from all services: {'; '.join(errors)}"
        )


def _endpoint_is_advertisable(certificate_service: Any) -> bool:
    if certificate_service is None:
        return True
    return bool(certificate_service.endpoint_is_advertisable())


def _provider_endpoint(settings: Any, host: str) -> tuple[str, str, int, str]:
    if bool(getattr(settings, "DEV_MODE", False)) and not bool(
        getattr(settings, "SECURE_SETUP_IN_DEVELOPMENT", False)
    ):
        port = int(getattr(settings, "PORT", 7466))
        return "http", host, port, _endpoint_url("http", host, port, 80)

    port = int(getattr(settings, "PUBLIC_HTTPS_PORT", 443))
    return "https", host, port, _endpoint_url("https", host, port, 443)


def _endpoint_url(protocol: str, host: str, port: int, default_port: int) -> str:
    if int(port) == int(default_port):
        return f"{protocol}://{host}"
    return f"{protocol}://{host}:{port}"


def _platform() -> Optional[str]:
    import platform as _plat

    raw = (_plat.machine() or "").lower()
    if not raw:
        return None
    if "aarch64" in raw or "arm64" in raw or raw.startswith("arm"):
        return "arm64"
    if "x86_64" in raw or "amd64" in raw or "x64" in raw:
        return "x86_64"
    return raw
