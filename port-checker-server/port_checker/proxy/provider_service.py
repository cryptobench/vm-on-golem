import logging

from port_checker.config import Settings
from port_checker.errors import (
    ForbiddenError,
    PayloadTooLargeError,
    ProxyDisabledError,
    ValidationError,
)

from .arkiv_resolver import ArkivResolver
from .central_resolver import CentralDiscoveryResolver
from .domain import ProviderProxyCommand, ProxyResponse
from .forwarder import HTTPForwarder
from .policy import (
    PROVIDER_CONTROL_HEADERS,
    append_query,
    forwarded_headers,
    forwarded_query,
    is_allowed_port,
    is_public_ip,
    normalize_proxy_source,
    parse_allowed_ports,
)

logger = logging.getLogger(__name__)


class ProviderProxyService:
    def __init__(
        self,
        settings: Settings,
        central_resolver: CentralDiscoveryResolver | None = None,
        arkiv_resolver: ArkivResolver | None = None,
        forwarder: HTTPForwarder | None = None,
    ) -> None:
        self.settings = settings
        self.central_resolver = central_resolver or CentralDiscoveryResolver(settings)
        self.arkiv_resolver = arkiv_resolver or ArkivResolver(settings)
        self.forwarder = forwarder or HTTPForwarder(settings)
        self.allowed_port_ranges = parse_allowed_ports(settings.proxy_allowed_ports)

    async def proxy(self, command: ProviderProxyCommand) -> ProxyResponse:
        self._validate_common(command.token, command.body)
        url, headers = await self.build_target(
            provider_id=command.provider_id,
            path=command.path,
            query=command.query,
            headers=command.headers,
            client_host=command.client_host,
            port=command.port,
            source=command.source,
            token=command.token,
            arkiv_rpc_url=command.arkiv_rpc_url,
            arkiv_ws_url=command.arkiv_ws_url,
            scheme="http",
        )
        response = await self.forwarder.forward(
            method=command.method,
            url=url,
            headers=headers,
            body=command.body,
        )
        response.headers["X-Proxy-Provider-Id"] = command.provider_id
        logger.info(
            "Proxied provider request",
            extra={
                "provider_id": command.provider_id,
                "source": normalize_proxy_source(command.source),
                "port": command.port,
                "method": command.method,
                "path": command.path,
                "status_code": response.status_code,
            },
        )
        return response

    async def build_target(
        self,
        *,
        provider_id: str,
        path: str,
        query: str,
        headers: dict[str, str],
        client_host: str,
        port: int,
        source: str | None,
        token: str | None,
        arkiv_rpc_url: str | None,
        arkiv_ws_url: str | None,
        scheme: str,
    ) -> tuple[str, dict[str, str]]:
        self._validate_common(token, b"")
        if not is_allowed_port(port, self.allowed_port_ranges):
            logger.warning(
                "Rejected provider proxy request for disallowed port",
                extra={"provider_id": provider_id, "port": port},
            )
            raise ForbiddenError("Target port not allowed")

        source = normalize_proxy_source(source)
        logger.debug(
            "Resolving provider proxy target",
            extra={"provider_id": provider_id, "source": source, "port": port},
        )
        if source == "central":
            ip = await self.central_resolver.resolve_ip(provider_id)
        else:
            ip = await self.arkiv_resolver.resolve_ip(
                provider_id,
                arkiv_rpc_url,
                arkiv_ws_url,
            )

        if not ip or (
            not is_public_ip(ip) and not self.settings.effective_allow_local_ips
        ):
            logger.warning(
                "Rejected provider proxy request with invalid resolved IP",
                extra={"provider_id": provider_id, "source": source},
            )
            raise ValidationError("Resolved IP invalid or not public")

        query = forwarded_query(
            query,
            {"port", "proxy_token", "proxy_source", "arkiv_rpc_url", "arkiv_ws_url"},
        )
        url = append_query(f"{scheme}://{ip}:{port}/{path}", query)
        headers = forwarded_headers(
            headers,
            PROVIDER_CONTROL_HEADERS,
            client_host,
        )
        logger.debug(
            "Built provider proxy target",
            extra={
                "provider_id": provider_id,
                "source": source,
                "target_url": url,
                "header_names": sorted(headers.keys()),
            },
        )
        return url, headers

    def _validate_common(self, token: str | None, body: bytes) -> None:
        if not self.settings.proxy_enabled:
            logger.warning("Rejected provider proxy request because proxy is disabled")
            raise ProxyDisabledError("Proxy is disabled")
        if not self.settings.proxy_token or token != self.settings.proxy_token:
            logger.warning("Rejected provider proxy request with invalid token")
            raise ForbiddenError("Forbidden")
        if len(body) > self.settings.proxy_max_body_bytes:
            logger.warning(
                "Rejected provider proxy request with oversized body",
                extra={
                    "body_bytes": len(body),
                    "max_body_bytes": self.settings.proxy_max_body_bytes,
                },
            )
            raise PayloadTooLargeError("Request body too large")
