import logging

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

logger = logging.getLogger(__name__)


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
            logger.warning(
                "Rejected direct proxy request because direct IP mode is disabled"
            )
            raise ProxyDisabledError(
                "Direct IP proxying is disabled. Use /proxy/provider/{provider_id}/..."
            )

        forward = (command.forward_to or command.target or "").strip()
        if not forward or ":" not in forward:
            logger.warning("Rejected direct proxy request with missing target")
            raise ValidationError(
                "Missing X-Forward-To header or target query (expected <ip>:<port>)"
            )

        host, port_text = forward.rsplit(":", 1)
        try:
            port = int(port_text)
        except ValueError as exc:
            logger.warning("Rejected direct proxy request with invalid port")
            raise ValidationError("Invalid port in target") from exc

        if not is_public_ip(host) and not self.settings.effective_allow_local_ips:
            logger.warning("Rejected direct proxy request with non-public target IP")
            raise ValidationError("Target must be a public IP address")
        if not is_allowed_port(port, self.allowed_port_ranges):
            logger.warning(
                "Rejected direct proxy request for disallowed port",
                extra={"port": port},
            )
            raise ForbiddenError("Target port not allowed")

        protocol = (command.protocol or "http").lower()
        if protocol != "http":
            logger.warning(
                "Rejected direct proxy request with unsupported protocol",
                extra={"protocol": protocol},
            )
            raise ValidationError("Only 'http' protocol is supported")

        query = forwarded_query(command.query, {"target"})
        url = append_query(f"{protocol}://{host}:{port}/{command.path}", query)
        headers = forwarded_headers(
            command.headers,
            DIRECT_CONTROL_HEADERS,
            command.client_host,
        )
        logger.debug(
            "Built direct proxy target",
            extra={"target_url": url, "header_names": sorted(headers.keys())},
        )
        response = await self.forwarder.forward(
            method=command.method,
            url=url,
            headers=headers,
            body=command.body,
        )
        logger.info(
            "Proxied direct request",
            extra={
                "target_host": host,
                "target_port": port,
                "method": command.method,
                "path": command.path,
                "status_code": response.status_code,
            },
        )
        return response

    def _validate_common(self, token: str | None, body: bytes) -> None:
        if not self.settings.proxy_enabled:
            logger.warning("Rejected direct proxy request because proxy is disabled")
            raise ProxyDisabledError("Proxy is disabled")
        if not self.settings.proxy_token or token != self.settings.proxy_token:
            logger.warning("Rejected direct proxy request with invalid token")
            raise ForbiddenError("Forbidden")
        if len(body) > self.settings.proxy_max_body_bytes:
            logger.warning(
                "Rejected direct proxy request with oversized body",
                extra={
                    "body_bytes": len(body),
                    "max_body_bytes": self.settings.proxy_max_body_bytes,
                },
            )
            raise PayloadTooLargeError("Request body too large")
