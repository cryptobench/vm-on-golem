import asyncio
from typing import Optional

from .advertiser import Advertiser
from .golem_base_advertiser import GolemBaseAdvertiser
from .advertiser import DiscoveryServerAdvertiser
from .resource_tracker import ResourceTracker


class MultiAdvertiser(Advertiser):
    """Advertise to both Golem Base and the Discovery Server."""

    def __init__(self, resource_tracker: ResourceTracker):
        self.golem = GolemBaseAdvertiser(resource_tracker)
        self.discovery = DiscoveryServerAdvertiser(resource_tracker)

    async def initialize(self):
        await asyncio.gather(self.golem.initialize(), self.discovery.initialize())

    async def start_loop(self):
        await asyncio.gather(self.golem.start_loop(), self.discovery.start_loop())

    async def stop(self):
        await asyncio.gather(self.golem.stop(), self.discovery.stop())

    async def post_advertisement(self):
        await asyncio.gather(self.golem.post_advertisement(), self.discovery.post_advertisement())

