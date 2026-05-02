import asyncio

import aiohttp

from port_checker.config import Settings
from port_checker.errors import BadGatewayError, GatewayTimeoutError, NotFoundError


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
                async with session.get(url) as response:
                    if response.status != 200:
                        raise NotFoundError("Provider not found")
                    data = await response.json()
                    ip = data.get("ip_address") if isinstance(data, dict) else None
                    if not ip:
                        raise NotFoundError("Provider not found")
                    return str(ip)
            except asyncio.TimeoutError as exc:
                raise GatewayTimeoutError("Central discovery timeout") from exc
            except aiohttp.ClientError as exc:
                raise BadGatewayError(f"Central discovery error: {exc}") from exc
