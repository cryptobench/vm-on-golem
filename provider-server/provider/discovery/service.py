import asyncio
from typing import Optional

from .advertiser import Advertiser
from ..config import settings

class AdvertisementService:
    """Service for managing the advertisement lifecycle."""

    def __init__(self, advertiser: Advertiser):
        self.advertiser = advertiser
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Initialize and start the advertiser."""
        await self.advertiser.initialize()
        self._task = asyncio.create_task(self.advertiser.start_loop())

    async def stop(self):
        """Stop the advertiser."""
        if self._task:
            self._task.cancel()
            await self._task
        await self.advertiser.stop()

    async def trigger_update(self):
        """Trigger an immediate advertisement update."""
        try:
            await self.advertiser.post_advertisement()
        except Exception:
            pass
