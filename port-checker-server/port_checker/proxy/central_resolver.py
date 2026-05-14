import asyncio
import logging

import aiohttp

from port_checker.config import Settings
from port_checker.errors import BadGatewayError, GatewayTimeoutError, NotFoundError

logger = logging.getLogger(__name__)


class CentralDiscoveryResolver:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve_ip(self, provider_id: str) -> str:
        url = (
            f"{self.settings.central_discovery_api_url.rstrip('/')}"
            f"/advertisements/{provider_id}"
        )
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.settings.proxy_connect_timeout,
            sock_read=self.settings.proxy_read_timeout,
        )
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                logger.debug(
                    "Resolving provider through central discovery",
                    extra={"provider_id": provider_id, "url": url},
                )
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(
                            "Provider not found in central discovery",
                            extra={
                                "provider_id": provider_id,
                                "status_code": response.status,
                            },
                        )
                        raise NotFoundError("Provider not found")
                    data = await response.json()
                    ip = data.get("ip_address") if isinstance(data, dict) else None
                    if not ip:
                        logger.warning(
                            "Provider advertisement missing IP address",
                            extra={"provider_id": provider_id},
                        )
                        raise NotFoundError("Provider not found")
                    logger.debug(
                        "Resolved provider through central discovery",
                        extra={"provider_id": provider_id},
                    )
                    return str(ip)
            except asyncio.TimeoutError as exc:
                logger.error(
                    "Central discovery resolver timed out",
                    extra={"provider_id": provider_id, "url": url},
                )
                raise GatewayTimeoutError("Central discovery timeout") from exc
            except aiohttp.ClientError as exc:
                logger.error(
                    "Central discovery resolver failed",
                    extra={"provider_id": provider_id, "url": url, "error": str(exc)},
                )
                raise BadGatewayError(f"Central discovery error: {exc}") from exc
