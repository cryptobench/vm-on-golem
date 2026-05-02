import asyncio
import logging
from collections.abc import Awaitable, Callable

from .domain import PortCheckRequest, PortCheckResponse, PortStatus

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
        logger.info("Checking ports %s for IP %s", request.ports, request.provider_ip)
        results = await asyncio.gather(
            *[self.check_port(request.provider_ip, port) for port in request.ports]
        )
        port_results = dict(zip(request.ports, results))
        accessible_ports = sum(1 for status in results if status.accessible)
        message = f"Successfully verified {accessible_ports} out of {len(request.ports)} ports"
        logger.info("Port check summary: %s", message)
        return PortCheckResponse(
            success=accessible_ports > 0,
            results=port_results,
            message=message,
        )

    async def check_port(self, ip: str, port: int) -> PortStatus:
        last_error = None
        for attempt in range(self.retries):
            try:
                _, writer = await asyncio.wait_for(
                    self.open_connection(ip, port),
                    timeout=self.timeout,
                )
                writer.close()
                await writer.wait_closed()
                logger.info(
                    "Port %s is accessible (attempt %s/%s)",
                    port,
                    attempt + 1,
                    self.retries,
                )
                return PortStatus(accessible=True, error=None)
            except asyncio.TimeoutError:
                last_error = "Connection timed out"
                logger.warning(
                    "Port %s timed out (attempt %s/%s)",
                    port,
                    attempt + 1,
                    self.retries,
                )
            except ConnectionRefusedError:
                last_error = "Connection refused"
                logger.warning(
                    "Port %s connection refused (attempt %s/%s)",
                    port,
                    attempt + 1,
                    self.retries,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.error(
                    "Error checking port %s (attempt %s/%s): %s",
                    port,
                    attempt + 1,
                    self.retries,
                    last_error,
                )
            if attempt < self.retries - 1:
                await self.sleep(self.retry_delay)
        return PortStatus(accessible=False, error=last_error)
