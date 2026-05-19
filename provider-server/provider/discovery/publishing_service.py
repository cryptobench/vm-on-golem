import asyncio
import logging
from typing import Optional

from .publishers import DiscoveryPublisher

logger = logging.getLogger(__name__)


class DiscoveryPublishingService:
    """Service for managing the discovery publishing lifecycle."""

    def __init__(self, publisher: DiscoveryPublisher):
        self.publisher = publisher
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Initialize and start the publisher."""
        logger.info("Starting discovery publisher")
        await self.publisher.initialize()
        self._task = asyncio.create_task(self.publisher.start_loop())
        logger.info("Discovery publisher loop started")

    async def stop(self):
        """Stop the publisher."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.publisher.stop()
        logger.info("Discovery publisher stopped")

    async def trigger_update(self):
        """Trigger an immediate advertisement update."""
        logger.debug("Triggering discovery advertisement update")
        await self.publisher.post_advertisement()
