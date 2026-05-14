import asyncio
import logging
from typing import Any

from .arkiv_publisher import ArkivDiscoveryPublisher
from .publishers import CentralDiscoveryPublisher, DiscoveryPublisher
from .resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)


class CompositeDiscoveryPublisher(DiscoveryPublisher):
    """Publish to both Arkiv and the centralized discovery service."""

    def __init__(
        self,
        resource_tracker: ResourceTracker,
        certificate_service: Any = None,
    ):
        self.arkiv = ArkivDiscoveryPublisher(
            resource_tracker,
            certificate_service=certificate_service,
        )
        self.central = CentralDiscoveryPublisher(
            resource_tracker,
            certificate_service=certificate_service,
        )

    async def initialize(self):
        await self._run_both("initialize")

    async def start_loop(self):
        await self._run_both("start_loop")

    async def stop(self):
        await self._run_both("stop")

    async def post_advertisement(self):
        await self._run_both("post_advertisement")

    async def _run_both(self, method_name: str) -> None:
        results = await asyncio.gather(
            getattr(self.arkiv, method_name)(),
            getattr(self.central, method_name)(),
            return_exceptions=True,
        )
        failures = [
            (backend, result)
            for backend, result in zip(("arkiv", "central"), results)
            if isinstance(result, Exception)
        ]
        for backend, exc in failures:
            logger.warning(
                "Discovery backend operation failed",
                extra={"backend": backend, "operation": method_name, "error": str(exc)},
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        if len(failures) == len(results):
            logger.error(
                "All discovery backends failed", extra={"operation": method_name}
            )
            raise RuntimeError(f"all discovery backends failed during {method_name}")
