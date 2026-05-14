import asyncio
import logging
import time

import aiohttp
from fastapi import WebSocket

from port_checker.config import Settings
from port_checker.errors import BadGatewayError, GatewayTimeoutError

from .domain import ProxyResponse
from .policy import response_headers

logger = logging.getLogger(__name__)


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
                started_at = time.perf_counter()
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body if body else None,
                    allow_redirects=False,
                ) as resp:
                    headers_out = response_headers(dict(resp.headers))
                    headers_out["X-Proxy"] = "golem-port-checker"
                    content = await resp.read()
                    elapsed = time.perf_counter() - started_at
                    log = logger.warning if resp.status >= 400 else logger.debug
                    log(
                        "Forwarded HTTP proxy request",
                        extra={
                            "method": method,
                            "url": url,
                            "status_code": resp.status,
                            "elapsed_seconds": round(elapsed, 3),
                        },
                    )
                    return ProxyResponse(
                        content=content,
                        status_code=resp.status,
                        headers=headers_out,
                    )
            except asyncio.TimeoutError as exc:
                logger.error(
                    "HTTP proxy upstream timeout", extra={"method": method, "url": url}
                )
                raise GatewayTimeoutError("Upstream timeout") from exc
            except aiohttp.ClientError as exc:
                logger.error(
                    "HTTP proxy upstream client error",
                    extra={"method": method, "url": url, "error": str(exc)},
                )
                raise BadGatewayError(f"Upstream error: {exc}") from exc


class WebSocketForwarder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def forward(
        self,
        *,
        websocket: WebSocket,
        url: str,
        headers: dict[str, str],
    ) -> None:
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.settings.proxy_connect_timeout,
            sock_read=None,
        )
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.ws_connect(url, headers=headers) as upstream:
                    await websocket.accept()
                    logger.info("WebSocket proxy opened", extra={"url": url})
                    client_task = asyncio.create_task(
                        self._client_to_upstream(websocket, upstream)
                    )
                    upstream_task = asyncio.create_task(
                        self._upstream_to_client(websocket, upstream)
                    )
                    done, pending = await asyncio.wait(
                        [client_task, upstream_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    for task in done:
                        task.result()
                    logger.info("WebSocket proxy closed", extra={"url": url})
        except aiohttp.ClientError as exc:
            logger.warning(
                "WebSocket proxy upstream error",
                extra={"url": url, "error": str(exc)},
            )
            await websocket.close(code=1011, reason=f"Upstream error: {exc}")
        except asyncio.TimeoutError:
            logger.warning("WebSocket proxy upstream timeout", extra={"url": url})
            await websocket.close(code=1011, reason="Upstream timeout")

    async def _client_to_upstream(
        self, websocket: WebSocket, upstream: aiohttp.ClientWebSocketResponse
    ) -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                logger.debug("WebSocket client disconnected")
                await upstream.close()
                return
            if "text" in message and message["text"] is not None:
                await upstream.send_str(message["text"])
            elif "bytes" in message and message["bytes"] is not None:
                await upstream.send_bytes(message["bytes"])

    async def _upstream_to_client(
        self, websocket: WebSocket, upstream: aiohttp.ClientWebSocketResponse
    ) -> None:
        async for message in upstream:
            if message.type == aiohttp.WSMsgType.TEXT:
                await websocket.send_text(message.data)
            elif message.type == aiohttp.WSMsgType.BINARY:
                await websocket.send_bytes(message.data)
            elif message.type in {
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            }:
                logger.debug(
                    "WebSocket upstream closed",
                    extra={"message_type": str(message.type)},
                )
                break
        await websocket.close()
