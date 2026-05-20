import asyncio
import ssl
from pathlib import Path

import aiohttp
from aiohttp import web

EXACT_PUBLIC_ROUTES = (
    "auth/requestor-sessions",
    "provider/info",
    "summary",
    "images",
    "payments/lease-quotes",
)
PREFIX_PUBLIC_ROUTES = ("vms",)


class HttpsEdgeServer:
    def __init__(
        self,
        host: str,
        port: int,
        cert_path: Path,
        key_path: Path,
        upstream_base_url: str,
    ):
        self.host = host
        self.port = port
        self.cert_path = cert_path
        self.key_path = key_path
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self._runner: web.AppRunner | None = None
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        app = web.Application(client_max_size=32 * 1024 * 1024)
        app.router.add_route("*", "/api/v1/{tail:.*}", self._proxy)
        app.router.add_get("/health", self._health)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(str(self.cert_path), str(self.key_path))
        site = web.TCPSite(self._runner, self.host, self.port, ssl_context=context)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _proxy(self, request: web.Request) -> web.StreamResponse:
        if self._session is None:
            return web.Response(status=503, text="HTTPS edge is not ready")
        tail = request.match_info["tail"]
        if not _is_public_route(tail):
            return web.Response(status=404, text="Not found")
        target = f"{self.upstream_base_url}/api/v1/{tail}"
        if request.query_string:
            target = f"{target}?{request.query_string}"
        if _is_websocket_upgrade(request):
            return await self._proxy_websocket(request, target)
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in {"host", "connection", "content-length"}
        }
        async with self._session.request(
            request.method,
            target,
            headers=headers,
            data=await request.read(),
        ) as response:
            body = await response.read()
            proxied = web.Response(status=response.status, body=body)
            for key, value in response.headers.items():
                if key.lower() not in {
                    "content-length",
                    "connection",
                    "transfer-encoding",
                }:
                    proxied.headers[key] = value
            return proxied

    async def _proxy_websocket(
        self, request: web.Request, target: str
    ) -> web.WebSocketResponse | web.Response:
        if self._session is None:
            return web.Response(status=503, text="HTTPS edge is not ready")
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower()
            not in {
                "host",
                "connection",
                "content-length",
                "upgrade",
                "sec-websocket-extensions",
                "sec-websocket-key",
                "sec-websocket-protocol",
                "sec-websocket-version",
            }
        }
        protocols = _websocket_protocols(request)
        try:
            upstream = await self._session.ws_connect(
                _websocket_target(target),
                headers=headers,
                protocols=protocols,
                autoping=True,
                autoclose=True,
            )
        except aiohttp.ClientError as exc:
            return web.Response(status=502, text=f"WebSocket upstream failed: {exc}")

        downstream = web.WebSocketResponse(
            protocols=protocols,
            autoping=True,
            autoclose=True,
        )
        await downstream.prepare(request)
        try:
            await _bridge_websockets(downstream, upstream)
        finally:
            await upstream.close()
        return downstream


def _is_public_route(tail: str) -> bool:
    if tail in EXACT_PUBLIC_ROUTES:
        return True
    return any(
        tail == prefix or tail.startswith(f"{prefix}/")
        for prefix in PREFIX_PUBLIC_ROUTES
    )


def _is_websocket_upgrade(request: web.Request) -> bool:
    return request.headers.get("upgrade", "").lower() == "websocket"


def _websocket_target(target: str) -> str:
    if target.startswith("https://"):
        return f"wss://{target[len('https://'):]}"
    if target.startswith("http://"):
        return f"ws://{target[len('http://'):]}"
    return target


def _websocket_protocols(request: web.Request) -> tuple[str, ...]:
    header = request.headers.get("Sec-WebSocket-Protocol", "")
    return tuple(protocol.strip() for protocol in header.split(",") if protocol.strip())


async def _bridge_websockets(
    downstream: web.WebSocketResponse,
    upstream: aiohttp.ClientWebSocketResponse,
) -> None:
    async def downstream_to_upstream() -> None:
        async for message in downstream:
            if message.type == aiohttp.WSMsgType.TEXT:
                await upstream.send_str(message.data)
            elif message.type == aiohttp.WSMsgType.BINARY:
                await upstream.send_bytes(message.data)
            elif message.type == aiohttp.WSMsgType.CLOSE:
                await upstream.close()
                break

    async def upstream_to_downstream() -> None:
        async for message in upstream:
            if message.type == aiohttp.WSMsgType.TEXT:
                await downstream.send_str(message.data)
            elif message.type == aiohttp.WSMsgType.BINARY:
                await downstream.send_bytes(message.data)
            elif message.type == aiohttp.WSMsgType.CLOSE:
                await downstream.close()
                break

    tasks = [
        asyncio.create_task(downstream_to_upstream()),
        asyncio.create_task(upstream_to_downstream()),
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*done, *pending, return_exceptions=True)
