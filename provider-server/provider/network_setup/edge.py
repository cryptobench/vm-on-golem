import ssl
from pathlib import Path

import aiohttp
from aiohttp import web


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


def _is_public_route(tail: str) -> bool:
    allowed = ("provider/info", "vms", "images")
    return any(tail == prefix or tail.startswith(f"{prefix}/") for prefix in allowed)
