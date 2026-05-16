import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Iterable

logger = logging.getLogger(__name__)

ProviderLiveScope = str


class ProviderEventBroadcaster:
    """In-process invalidation bus for provider live dashboard scopes."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[set[ProviderLiveScope]]] = set()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[set[ProviderLiveScope]]]:
        queue: asyncio.Queue[set[ProviderLiveScope]] = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def publish(self, scopes: Iterable[ProviderLiveScope]) -> None:
        payload = {str(scope) for scope in scopes if scope}
        if not payload:
            return
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    "Provider live subscriber queue full; coalescing update",
                    extra={"scopes": sorted(payload)},
                )
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                await queue.put(payload)
