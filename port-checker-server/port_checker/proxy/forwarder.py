import asyncio

import aiohttp

from port_checker.config import Settings
from port_checker.errors import BadGatewayError, GatewayTimeoutError

from .domain import ProxyResponse
from .policy import response_headers


class HTTPForwarder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def forward(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
    ) -> ProxyResponse:
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.settings.proxy_connect_timeout,
            sock_read=self.settings.proxy_read_timeout,
        )
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body if body else None,
                    allow_redirects=False,
                ) as resp:
                    headers_out = response_headers(dict(resp.headers))
                    headers_out["X-Proxy"] = "golem-port-checker"
                    return ProxyResponse(
                        content=await resp.read(),
                        status_code=resp.status,
                        headers=headers_out,
                    )
            except asyncio.TimeoutError as exc:
                raise GatewayTimeoutError("Upstream timeout") from exc
            except aiohttp.ClientError as exc:
                raise BadGatewayError(f"Upstream error: {exc}") from exc
