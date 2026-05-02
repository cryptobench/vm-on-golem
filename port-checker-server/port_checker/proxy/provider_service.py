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
        if not is_allowed_port(command.port, self.allowed_port_ranges):
            raise ForbiddenError("Target port not allowed")

        source = normalize_proxy_source(command.source)
        if source == "central":
            ip = await self.central_resolver.resolve_ip(command.provider_id)
        else:
            ip = await self.arkiv_resolver.resolve_ip(
                command.provider_id,
                command.arkiv_rpc_url,
                command.arkiv_ws_url,
            )

        if not ip or (
            not is_public_ip(ip) and not self.settings.effective_allow_local_ips
        ):
            raise ValidationError("Resolved IP invalid or not public")

        query = forwarded_query(command.query, {"port"})
        url = append_query(f"http://{ip}:{command.port}/{command.path}", query)
        headers = forwarded_headers(
            command.headers,
            PROVIDER_CONTROL_HEADERS,
            command.client_host,
        )
        response = await self.forwarder.forward(
            method=command.method,
            url=url,
            headers=headers,
            body=command.body,
        )
        response.headers["X-Proxy-Provider-Id"] = command.provider_id
        return response

    def _validate_common(self, token: str | None, body: bytes) -> None:
        if not self.settings.proxy_enabled:
            raise ProxyDisabledError("Proxy is disabled")
        if not self.settings.proxy_token or token != self.settings.proxy_token:
            raise ForbiddenError("Forbidden")
        if len(body) > self.settings.proxy_max_body_bytes:
            raise PayloadTooLargeError("Request body too large")
