import asyncio

from .arkiv_publisher import ArkivDiscoveryPublisher
from .publishers import CentralDiscoveryPublisher, DiscoveryPublisher
from .resource_tracker import ResourceTracker


class CompositeDiscoveryPublisher(DiscoveryPublisher):
    """Publish to both Arkiv and the centralized discovery service."""

    def __init__(self, resource_tracker: ResourceTracker):
        self.arkiv = ArkivDiscoveryPublisher(resource_tracker)
        self.central = CentralDiscoveryPublisher(resource_tracker)

    async def initialize(self):
        await asyncio.gather(self.arkiv.initialize(), self.central.initialize())

    async def start_loop(self):
        await asyncio.gather(self.arkiv.start_loop(), self.central.start_loop())

    async def stop(self):
        await asyncio.gather(self.arkiv.stop(), self.central.stop())

    async def post_advertisement(self):
        await asyncio.gather(
            self.arkiv.post_advertisement(), self.central.post_advertisement()
        )
