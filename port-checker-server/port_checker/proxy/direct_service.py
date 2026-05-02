from port_checker.config import Settings
from port_checker.errors import (
    ForbiddenError,
    PayloadTooLargeError,
    ProxyDisabledError,
    ValidationError,
)

from .domain import DirectProxyCommand, ProxyResponse
from .forwarder import HTTPForwarder
from .policy import (
    DIRECT_CONTROL_HEADERS,
    append_query,
    forwarded_headers,
    forwarded_query,
    is_allowed_port,
    is_public_ip,
    parse_allowed_ports,
)


class DirectProxyService:
    def __init__(
        self,
        settings: Settings,
        forwarder: HTTPForwarder | None = None,
    ) -> None:
        self.settings = settings
        self.forwarder = forwarder or HTTPForwarder(settings)
        self.allowed_port_ranges = parse_allowed_ports(settings.proxy_allowed_ports)

    async def proxy(self, command: DirectProxyCommand) -> ProxyResponse:
        self._validate_common(command.token, command.body)
        if not self.settings.proxy_allow_direct_ip:
            raise ProxyDisabledError(
                "Direct IP proxying is disabled. Use /proxy/provider/{provider_id}/..."
            )

        forward = (command.forward_to or command.target or "").strip()
        if not forward or ":" not in forward:
            raise ValidationError(
                "Missing X-Forward-To header or target query (expected <ip>:<port>)"
            )

        host, port_text = forward.rsplit(":", 1)
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValidationError("Invalid port in target") from exc

        if not is_public_ip(host) and not self.settings.effective_allow_local_ips:
            raise ValidationError("Target must be a public IP address")
        if not is_allowed_port(port, self.allowed_port_ranges):
            raise ForbiddenError("Target port not allowed")

        protocol = (command.protocol or "http").lower()
        if protocol != "http":
            raise ValidationError("Only 'http' protocol is supported")

        query = forwarded_query(command.query, {"target"})
        url = append_query(f"{protocol}://{host}:{port}/{command.path}", query)
        headers = forwarded_headers(
            command.headers,
            DIRECT_CONTROL_HEADERS,
            command.client_host,
        )
        return await self.forwarder.forward(
            method=command.method,
            url=url,
            headers=headers,
            body=command.body,
        )

    def _validate_common(self, token: str | None, body: bytes) -> None:
        if not self.settings.proxy_enabled:
            raise ProxyDisabledError("Proxy is disabled")
        if not self.settings.proxy_token or token != self.settings.proxy_token:
            raise ForbiddenError("Forbidden")
        if len(body) > self.settings.proxy_max_body_bytes:
            raise PayloadTooLargeError("Request body too large")
