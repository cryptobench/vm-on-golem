import asyncio
import ipaddress
import logging
import ssl
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from .domain import (
    PortCheckRequest,
    PortCheckResponse,
    PortStatus,
    TlsCheckRequest,
    TlsCheckResponse,
)

logger = logging.getLogger(__name__)

OpenConnection = Callable[[str, int], Awaitable[tuple[object, object]]]
Sleep = Callable[[float], Awaitable[None]]


class PortCheckService:
    def __init__(
        self,
        retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 5.0,
        open_connection: OpenConnection | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self.retries = retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.open_connection = open_connection or asyncio.open_connection
        self.sleep = sleep or asyncio.sleep

    async def check_ports(self, request: PortCheckRequest) -> PortCheckResponse:
        started_at = time.perf_counter()
        logger.info(
            "Checking ports %s for IP %s with retries=%s retry_delay=%.2fs timeout=%.2fs",
            request.ports,
            request.provider_ip,
            self.retries,
            self.retry_delay,
            self.timeout,
        )
        results = await asyncio.gather(
            *[self.check_port(request.provider_ip, port) for port in request.ports]
        )
        port_results = dict(zip(request.ports, results))
        accessible_ports = sum(1 for status in results if status.accessible)
        message = f"Successfully verified {accessible_ports} out of {len(request.ports)} ports"
        logger.info(
            "Port check summary: %s elapsed=%.2fs",
            message,
            time.perf_counter() - started_at,
        )
        return PortCheckResponse(
            success=accessible_ports > 0,
            results=port_results,
            message=message,
        )

    async def check_port(self, ip: str, port: int) -> PortStatus:
        last_error = None
        for attempt in range(self.retries):
            started_at = time.perf_counter()
            logger.debug(
                "Checking port %s at %s (attempt %s/%s, timeout=%.2fs)",
                port,
                ip,
                attempt + 1,
                self.retries,
                self.timeout,
            )
            try:
                _, writer = await asyncio.wait_for(
                    self.open_connection(ip, port),
                    timeout=self.timeout,
                )
                writer.close()
                await writer.wait_closed()
                logger.debug(
                    "Port %s is accessible (attempt %s/%s, elapsed=%.2fs)",
                    port,
                    attempt + 1,
                    self.retries,
                    time.perf_counter() - started_at,
                )
                return PortStatus(accessible=True, error=None)
            except asyncio.TimeoutError:
                last_error = "Connection timed out"
                logger.debug(
                    "Port %s timed out (attempt %s/%s, elapsed=%.2fs)",
                    port,
                    attempt + 1,
                    self.retries,
                    time.perf_counter() - started_at,
                )
            except ConnectionRefusedError:
                last_error = "Connection refused"
                logger.debug(
                    "Port %s connection refused (attempt %s/%s, elapsed=%.2fs)",
                    port,
                    attempt + 1,
                    self.retries,
                    time.perf_counter() - started_at,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.error(
                    "Error checking port %s (attempt %s/%s, elapsed=%.2fs): %s",
                    port,
                    attempt + 1,
                    self.retries,
                    time.perf_counter() - started_at,
                    last_error,
                )
            if attempt < self.retries - 1:
                await self.sleep(self.retry_delay)
        logger.warning("Port %s is inaccessible at %s: %s", port, ip, last_error)
        return PortStatus(accessible=False, error=last_error)

    async def check_tls(self, request: TlsCheckRequest) -> TlsCheckResponse:
        peer = f"{request.host}:{request.port}"
        context = ssl.create_default_context()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    request.host,
                    request.port,
                    ssl=context,
                    server_hostname=request.host,
                ),
                timeout=self.timeout,
            )
            ssl_object = writer.get_extra_info("ssl_object")
            peer_cert = ssl_object.getpeercert() if ssl_object else None
            writer.close()
            await writer.wait_closed()
            if not peer_cert:
                logger.warning("TLS check failed for %s: no certificate", peer)
                return TlsCheckResponse(valid=False, peer=peer, error="no certificate")
            not_after_text = peer_cert.get("notAfter")
            not_after = (
                datetime.fromtimestamp(
                    ssl.cert_time_to_seconds(not_after_text), timezone.utc
                )
                if not_after_text
                else None
            )
            if not_after is None:
                logger.warning(
                    "TLS check failed for %s: certificate missing expiry", peer
                )
                return TlsCheckResponse(
                    valid=False,
                    peer=peer,
                    error="certificate missing expiry",
                )
            if not_after <= datetime.now(timezone.utc):
                logger.warning("TLS check failed for %s: certificate expired", peer)
                return TlsCheckResponse(
                    valid=False,
                    peer=peer,
                    error="certificate expired",
                    not_after=not_after.isoformat(),
                )
            if request.expected_ip:
                expected = ipaddress.ip_address(request.expected_ip)
                san_ips = [
                    ipaddress.ip_address(value)
                    for kind, value in peer_cert.get("subjectAltName", ())
                    if kind == "IP Address"
                ]
                if expected not in san_ips:
                    logger.warning(
                        "TLS check failed for %s: certificate does not match expected IP",
                        peer,
                    )
                    return TlsCheckResponse(
                        valid=False,
                        peer=peer,
                        error="certificate does not match expected IP",
                        not_after=not_after.isoformat(),
                    )
            return TlsCheckResponse(
                valid=True,
                peer=peer,
                not_after=not_after.isoformat(),
            )
        except Exception as exc:
            logger.warning("TLS check failed for %s: %s", peer, exc)
            return TlsCheckResponse(valid=False, peer=peer, error=str(exc))
