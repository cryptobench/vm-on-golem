import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from provider.monitoring.domain import MetricScope

from .domain import LiveScope, LiveSnapshot

logger = logging.getLogger(__name__)

VALID_HISTORY_RANGES = {"1h", "6h", "24h", "7d", "30d"}
SNAPSHOT_SCOPES: tuple[LiveScope, ...] = (
    "provider_info",
    "lifecycle",
    "access",
    "job",
    "snapshots",
    "stream",
    "metrics",
)


class VMLiveService:
    """Build and stream the live read model for a VM details page."""

    def __init__(
        self,
        monitoring_service: Any,
        vm_application_service: Any,
        provider_info_service: Any,
        stream_status_service: Any,
    ):
        self.monitoring_service = monitoring_service
        self.vm_application_service = vm_application_service
        self.provider_info_service = provider_info_service
        self.stream_status_service = stream_status_service

    async def stream_vm(
        self,
        websocket: WebSocket,
        vm_id: str,
        history_range: str = "1h",
        job_id: str | None = None,
    ) -> None:
        history_range = self._normalize_history_range(history_range)
        await websocket.accept()
        logger.info(
            "VM live stream opened",
            extra={"vm_id": vm_id, "history_range": history_range, "job_id": job_id},
        )
        async with self.monitoring_service.watch_vm(vm_id):
            await self._send(
                websocket,
                "hello",
                data={
                    "protocol": "vm-live.v1",
                    "capabilities": {
                        "scopes": list(SNAPSHOT_SCOPES),
                        "client_events": ["set_history_range", "refresh", "ping"],
                    },
                    "server_time": self._now(),
                    "guest_interval_seconds": self.monitoring_service.guest_sample_interval(
                        vm_id
                    ),
                    "live_mode": self.monitoring_service.is_vm_live(vm_id),
                },
            )
            await self._send_snapshot(websocket, vm_id, history_range, job_id)
            async with self.monitoring_service.subscribe_vm_metrics(vm_id) as queue:
                tasks = [
                    asyncio.create_task(
                        self._receive_loop(websocket, vm_id, history_range, job_id),
                        name=f"vm-live-recv:{vm_id}",
                    ),
                    asyncio.create_task(
                        self._metrics_loop(websocket, queue),
                        name=f"vm-live-metrics:{vm_id}",
                    ),
                    asyncio.create_task(
                        self._poll_loop(websocket, vm_id, job_id),
                        name=f"vm-live-poll:{vm_id}",
                    ),
                    asyncio.create_task(
                        self._heartbeat_loop(websocket),
                        name=f"vm-live-heartbeat:{vm_id}",
                    ),
                ]
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exc = task.exception()
                    if exc and not isinstance(exc, WebSocketDisconnect):
                        logger.debug(
                            "VM live task ended",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )
        logger.info("VM live stream closed", extra={"vm_id": vm_id})

    async def _receive_loop(
        self,
        websocket: WebSocket,
        vm_id: str,
        history_range: str,
        job_id: str | None,
    ) -> None:
        current_range = history_range
        while True:
            message = await websocket.receive_json()
            event_type = str(message.get("type") or "")
            if event_type == "ping":
                await self._send(
                    websocket, "heartbeat", data={"server_time": self._now()}
                )
            elif event_type == "set_history_range":
                current_range = self._normalize_history_range(
                    str(message.get("history_range") or current_range)
                )
                await self._send_update(
                    websocket,
                    "metrics",
                    await self._metrics_payload(vm_id, current_range),
                )
            elif event_type == "refresh":
                scopes = message.get("scopes") or list(SNAPSHOT_SCOPES)
                await self._refresh_scopes(
                    websocket, vm_id, current_range, job_id, scopes
                )
            else:
                logger.warning(
                    "Unsupported VM live event",
                    extra={"vm_id": vm_id, "event_type": event_type},
                )
                await self._send(
                    websocket,
                    "error",
                    error=f"unsupported live event: {event_type or 'unknown'}",
                )

    async def _metrics_loop(
        self, websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        while True:
            payload = await queue.get()
            await self._send_update(websocket, "metrics", payload)

    async def _poll_loop(
        self, websocket: WebSocket, vm_id: str, job_id: str | None
    ) -> None:
        previous: dict[str, str] = {}
        while True:
            await asyncio.sleep(2)
            for scope in (
                "provider_info",
                "lifecycle",
                "access",
                "job",
                "snapshots",
                "stream",
            ):
                if scope == "job" and not job_id:
                    continue
                try:
                    data = await self._scope_data(scope, vm_id, job_id)
                    fingerprint = json.dumps(data, sort_keys=True, default=str)
                    if previous.get(scope) != fingerprint:
                        previous[scope] = fingerprint
                        await self._send_update(websocket, scope, data)
                except Exception as exc:
                    fingerprint = f"error:{exc}"
                    if previous.get(scope) != fingerprint:
                        previous[scope] = fingerprint
                        await self._send_error(websocket, scope, exc)

    async def _heartbeat_loop(self, websocket: WebSocket) -> None:
        while True:
            await asyncio.sleep(15)
            await self._send(websocket, "heartbeat", data={"server_time": self._now()})

    async def _send_snapshot(
        self,
        websocket: WebSocket,
        vm_id: str,
        history_range: str,
        job_id: str | None,
    ) -> None:
        snapshot = await self._snapshot(vm_id, history_range, job_id)
        await self._send(websocket, "snapshot", data=snapshot.model_dump(mode="json"))

    async def _snapshot(
        self, vm_id: str, history_range: str, job_id: str | None
    ) -> LiveSnapshot:
        snapshot = LiveSnapshot()
        for scope in SNAPSHOT_SCOPES:
            if scope == "job" and not job_id:
                continue
            try:
                if scope == "metrics":
                    payload = await self._metrics_payload(vm_id, history_range)
                    snapshot.metrics_latest = payload["latest"]
                    snapshot.metrics_history = payload["history"]
                else:
                    setattr(
                        snapshot, scope, await self._scope_data(scope, vm_id, job_id)
                    )
            except Exception as exc:
                snapshot.errors[scope] = str(exc)
        return snapshot

    async def _refresh_scopes(
        self,
        websocket: WebSocket,
        vm_id: str,
        history_range: str,
        job_id: str | None,
        scopes: list[Any],
    ) -> None:
        for raw_scope in scopes:
            scope = str(raw_scope)
            if scope not in SNAPSHOT_SCOPES:
                await self._send(
                    websocket, "error", error=f"unsupported scope: {scope}"
                )
                continue
            if scope == "job" and not job_id:
                continue
            try:
                data = (
                    await self._metrics_payload(vm_id, history_range)
                    if scope == "metrics"
                    else await self._scope_data(scope, vm_id, job_id)
                )
                await self._send_update(websocket, scope, data)
            except Exception as exc:
                await self._send_error(websocket, scope, exc)

    async def _scope_data(
        self, scope: str, vm_id: str, job_id: str | None
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        if scope == "provider_info":
            return self.provider_info_service.get_info().model_dump(mode="json")
        if scope == "lifecycle":
            return (await self.vm_application_service.get_vm_status(vm_id)).model_dump(
                mode="json"
            )
        if scope == "access":
            result = await self.vm_application_service.get_vm_access(vm_id)
            return (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else dict(result)
            )
        if scope == "job":
            return await self.vm_application_service.get_create_job(str(job_id))
        if scope == "snapshots":
            return [
                snapshot.model_dump(mode="json")
                for snapshot in await self.vm_application_service.list_snapshots(vm_id)
            ]
        if scope == "stream":
            return (
                await self.stream_status_service.get_vm_stream_status(vm_id)
            ).model_dump(mode="json")
        raise ValueError(f"unsupported scope: {scope}")

    async def _metrics_payload(self, vm_id: str, history_range: str) -> dict[str, Any]:
        return {
            "latest": self.monitoring_service.latest_for_vm(vm_id).model_dump(
                mode="json"
            ),
            "history": self.monitoring_service.history(
                scope=MetricScope.VM,
                range_name=history_range,
                vm_id=vm_id,
            ).model_dump(mode="json"),
            "guest_interval_seconds": self.monitoring_service.guest_sample_interval(
                vm_id
            ),
            "live_mode": self.monitoring_service.is_vm_live(vm_id),
        }

    async def _send_update(
        self,
        websocket: WebSocket,
        scope: str,
        data: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> None:
        await self._send(websocket, "update", scope=scope, data=data)

    async def _send_error(
        self, websocket: WebSocket, scope: str, exc: Exception
    ) -> None:
        await self._send(websocket, "error", scope=scope, error=str(exc))

    async def _send(
        self,
        websocket: WebSocket,
        event_type: str,
        *,
        scope: str | None = None,
        data: dict[str, Any] | list[Any] | None = None,
        error: str | None = None,
    ) -> None:
        await websocket.send_json(
            {
                "type": event_type,
                "generated_at": self._now(),
                "scope": scope,
                "data": data,
                "error": error,
            }
        )

    @staticmethod
    def _normalize_history_range(history_range: str) -> str:
        return history_range if history_range in VALID_HISTORY_RANGES else "1h"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
