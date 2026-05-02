import asyncio
from typing import Optional

from .publishers import DiscoveryPublisher


class DiscoveryPublishingService:
    """Service for managing the discovery publishing lifecycle."""

    def __init__(self, publisher: DiscoveryPublisher):
        self.publisher = publisher
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Initialize and start the publisher."""
        await self.publisher.initialize()
        self._task = asyncio.create_task(self.publisher.start_loop())

    async def stop(self):
        """Stop the publisher."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.publisher.stop()

    async def trigger_update(self):
        """Trigger an immediate advertisement update."""
        await self.publisher.post_advertisement()
