import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Iterable

logger = logging.getLogger(__name__)

LiveScope = str


class LiveInvalidationBus:
    """In-process invalidation bus for provider-wide and VM-scoped live scopes."""

    def __init__(self) -> None:
        self._provider_subscribers: set[asyncio.Queue[set[LiveScope]]] = set()
        self._vm_subscribers: dict[str, set[asyncio.Queue[set[LiveScope]]]] = {}

    @asynccontextmanager
    async def subscribe_provider(self) -> AsyncIterator[asyncio.Queue[set[LiveScope]]]:
        queue: asyncio.Queue[set[LiveScope]] = asyncio.Queue(maxsize=32)
        self._provider_subscribers.add(queue)
        try:
            yield queue
        finally:
            self._provider_subscribers.discard(queue)

    @asynccontextmanager
    async def subscribe_vm(
        self, vm_id: str
    ) -> AsyncIterator[asyncio.Queue[set[LiveScope]]]:
        queue: asyncio.Queue[set[LiveScope]] = asyncio.Queue(maxsize=32)
        subscribers = self._vm_subscribers.setdefault(vm_id, set())
        subscribers.add(queue)
        try:
            yield queue
        finally:
            subscribers.discard(queue)
            if not subscribers:
                self._vm_subscribers.pop(vm_id, None)

    async def publish(self, scopes: Iterable[LiveScope]) -> None:
        await self.publish_provider(scopes)

    async def publish_provider(self, scopes: Iterable[LiveScope]) -> None:
        payload = self._payload(scopes)
        if not payload:
            return
        await self._publish(
            list(self._provider_subscribers),
            payload,
            "Provider live subscriber queue full; coalescing update",
        )

    async def publish_vm(self, vm_id: str, scopes: Iterable[LiveScope]) -> None:
        payload = self._payload(scopes)
        if not payload:
            return
        await self._publish(
            list(self._vm_subscribers.get(vm_id, set())),
            payload,
            "VM live subscriber queue full; coalescing update",
            extra={"vm_id": vm_id},
        )

    @staticmethod
    def _payload(scopes: Iterable[LiveScope]) -> set[LiveScope]:
        return {str(scope) for scope in scopes if scope}

    @staticmethod
    async def _publish(
        queues: list[asyncio.Queue[set[LiveScope]]],
        payload: set[LiveScope],
        warning: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    warning,
                    extra={**(extra or {}), "scopes": sorted(payload)},
                )
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                await queue.put(payload)


ProviderLiveScope = LiveScope
ProviderEventBroadcaster = LiveInvalidationBus
