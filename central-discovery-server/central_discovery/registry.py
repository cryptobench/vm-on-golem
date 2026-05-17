import asyncio
from dataclasses import dataclass, field
from typing import Dict, Iterable, Set

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from central_discovery.domain import (
    Advertisement,
    AdvertisementPayload,
    ResourceRequirements,
)
from central_discovery.time import utc_now


@dataclass
class RequestorConnection:
    websocket: WebSocket
    filters: ResourceRequirements = field(default_factory=ResourceRequirements)
    visible_provider_ids: Set[str] = field(default_factory=set)


class DiscoveryRegistry:
    def __init__(self):
        self._advertisements: Dict[str, Advertisement] = {}
        self._requestors: Dict[int, RequestorConnection] = {}
        self._lock = asyncio.Lock()

    async def upsert_provider(
        self, provider_id: str, payload: AdvertisementPayload
    ) -> Advertisement:
        async with self._lock:
            existing = self._advertisements.get(provider_id)
            now = utc_now()
            advertisement = Advertisement(
                provider_id=provider_id,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                **payload.dict(),
            )
            self._advertisements[provider_id] = advertisement
            requestors = list(self._requestors.values())

        await self._broadcast_upsert(advertisement, requestors)
        return advertisement

    async def remove_provider(self, provider_id: str) -> bool:
        async with self._lock:
            removed = self._advertisements.pop(provider_id, None)
            requestors = list(self._requestors.values())

        if removed is None:
            return False
        await self._broadcast_remove(provider_id, requestors)
        return True

    async def subscribe(
        self, websocket: WebSocket, filters: ResourceRequirements
    ) -> list[Advertisement]:
        async with self._lock:
            connection_key = id(websocket)
            connection = self._requestors.get(connection_key)
            if connection is None:
                connection = RequestorConnection(websocket=websocket)
                self._requestors[connection_key] = connection
            connection.filters = filters
            matching = [
                advertisement
                for advertisement in self._advertisements.values()
                if matches_filters(advertisement, filters)
            ]
            connection.visible_provider_ids = {
                advertisement.provider_id for advertisement in matching
            }
            return matching

    async def disconnect_requestor(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._requestors.pop(id(websocket), None)

    async def snapshot(self, filters: ResourceRequirements) -> list[Advertisement]:
        async with self._lock:
            return [
                advertisement
                for advertisement in self._advertisements.values()
                if matches_filters(advertisement, filters)
            ]

    async def clear(self) -> None:
        async with self._lock:
            self._advertisements.clear()
            for requestor in self._requestors.values():
                requestor.visible_provider_ids.clear()

    async def _broadcast_upsert(
        self,
        advertisement: Advertisement,
        requestors: Iterable[RequestorConnection],
    ) -> None:
        for requestor in requestors:
            matches = matches_filters(advertisement, requestor.filters)
            was_visible = advertisement.provider_id in requestor.visible_provider_ids
            if matches:
                requestor.visible_provider_ids.add(advertisement.provider_id)
                await send_event(
                    requestor.websocket,
                    "provider.upsert",
                    {"advertisement": advertisement.dict()},
                )
            elif was_visible:
                requestor.visible_provider_ids.discard(advertisement.provider_id)
                await send_event(
                    requestor.websocket,
                    "provider.remove",
                    {"provider_id": advertisement.provider_id},
                )

    async def _broadcast_remove(
        self, provider_id: str, requestors: Iterable[RequestorConnection]
    ) -> None:
        for requestor in requestors:
            if provider_id not in requestor.visible_provider_ids:
                continue
            requestor.visible_provider_ids.discard(provider_id)
            await send_event(
                requestor.websocket,
                "provider.remove",
                {"provider_id": provider_id},
            )


async def send_event(websocket: WebSocket, event_type: str, payload: dict) -> None:
    await websocket.send_json(
        jsonable_encoder(
            {"type": event_type, "generated_at": utc_now().isoformat(), **payload}
        )
    )


def matches_filters(
    advertisement: Advertisement, filters: ResourceRequirements
) -> bool:
    resources = advertisement.resources
    if filters.cpu is not None and resources["cpu"] < filters.cpu:
        return False
    if filters.memory is not None and resources["memory"] < filters.memory:
        return False
    if filters.storage is not None and resources["storage"] < filters.storage:
        return False
    if filters.country and advertisement.country.upper() != filters.country.upper():
        return False
    if filters.platform and advertisement.platform != filters.platform:
        return False
    return True
