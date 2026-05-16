import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from websockets.exceptions import ConnectionClosed

from provider.auth.errors import AuthError
from provider.errors import ValidationError
from provider.monitoring.domain import MetricHistoryRange, MetricScope
from provider.utils.time import ensure_utc

from .domain import LiveScope, LiveSnapshot
from .events import ProviderEventBroadcaster

logger = logging.getLogger(__name__)

HISTORY_RANGE_CLOSE_CODE = 1008
AUTH_CLOSE_CODE = 1008
AUTH_TIMEOUT_SECONDS = 10
SNAPSHOT_SCOPES: tuple[LiveScope, ...] = (
    "provider_info",
    "lifecycle",
    "access",
    "job",
    "snapshots",
    "stream",
    "metrics",
)
PROVIDER_LIVE_SCOPES: tuple[str, ...] = (
    "provider_info",
    "summary",
    "vms",
    "streams",
    "monitoring",
    "metrics",
    "alerts",
    "alert_rules",
    "webhooks",
)


def _is_websocket_disconnect(exc: BaseException | None) -> bool:
    if exc is None:
        return False
    if isinstance(exc, (WebSocketDisconnect, ConnectionClosed)):
        return True
    message = str(exc)
    return isinstance(exc, RuntimeError) and (
        'Cannot call "send"' in message or "Unexpected ASGI message" in message
    )


def _task_exception(task: asyncio.Task[Any]) -> BaseException | None:
    try:
        return task.exception()
    except asyncio.CancelledError:
        return None


def _validate_history_range(history_range: str | MetricHistoryRange) -> str:
    if isinstance(history_range, MetricHistoryRange):
        return history_range.value
    try:
        return MetricHistoryRange(str(history_range)).value
    except ValueError as exc:
        supported = ", ".join(MetricHistoryRange.values())
        raise ValidationError(
            f"invalid metrics history range: {history_range}. "
            f"Supported ranges: {supported}"
        ) from exc


class VMLiveService:
    """Build and stream the live read model for a VM details page."""

    def __init__(
        self,
        monitoring_service: Any,
        vm_application_service: Any,
        provider_info_service: Any,
        stream_status_service: Any,
        auth_service: Any,
    ):
        self.monitoring_service = monitoring_service
        self.vm_application_service = vm_application_service
        self.provider_info_service = provider_info_service
        self.stream_status_service = stream_status_service
        self.auth_service = auth_service

    async def stream_vm(
        self,
        websocket: WebSocket,
        vm_id: str,
        history_range: str = "1h",
        job_id: str | None = None,
    ) -> None:
        await websocket.accept()
        if not await self._authorize(websocket, vm_id):
            return
        try:
            history_range = _validate_history_range(history_range)
        except ValidationError as exc:
            await self._send(websocket, "error", scope="metrics", error=str(exc))
            await websocket.close(code=HISTORY_RANGE_CLOSE_CODE)
            return
        logger.info(
            "VM live stream opened",
            extra={"vm_id": vm_id, "history_range": history_range, "job_id": job_id},
        )
        try:
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
                        exc = _task_exception(task)
                        if exc and not _is_websocket_disconnect(exc):
                            logger.debug(
                                "VM live task ended",
                                exc_info=(type(exc), exc, exc.__traceback__),
                            )
                        if _is_websocket_disconnect(exc):
                            break
        except WebSocketDisconnect:
            logger.debug("VM live stream disconnected", extra={"vm_id": vm_id})
        finally:
            logger.info("VM live stream closed", extra={"vm_id": vm_id})

    async def _authorize(self, websocket: WebSocket, vm_id: str) -> bool:
        try:
            message = await asyncio.wait_for(
                websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS
            )
            if str(message.get("type") or "") != "auth":
                raise ValidationError("VM live auth message required")
            token = str(message.get("token") or "")
            identity = self.auth_service.validate_requestor_token(token)
            await self.auth_service.require_vm_access(identity, vm_id)
            return True
        except (AuthError, ValidationError, asyncio.TimeoutError) as exc:
            await self._send(websocket, "error", error=str(exc))
            await websocket.close(code=AUTH_CLOSE_CODE)
            return False

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
                try:
                    current_range = _validate_history_range(
                        str(message.get("history_range") or current_range)
                    )
                except ValidationError as exc:
                    await self._send_error(websocket, "metrics", exc)
                    continue
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
        try:
            await websocket.send_json(
                {
                    "type": event_type,
                    "generated_at": self._now(),
                    "scope": scope,
                    "data": data,
                    "error": error,
                }
            )
        except Exception as exc:
            if _is_websocket_disconnect(exc):
                raise WebSocketDisconnect() from exc
            raise

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


class ProviderLiveService:
    """Build and stream the provider desktop live dashboard read model."""

    def __init__(
        self,
        *,
        broadcaster: ProviderEventBroadcaster,
        provider_info_service: Any,
        summary_service: Any,
        vm_application_service: Any,
        stream_status_service: Any,
        monitoring_service: Any,
        auth_service: Any,
        webhook_service: Any = None,
    ):
        self.broadcaster = broadcaster
        self.provider_info_service = provider_info_service
        self.summary_service = summary_service
        self.vm_application_service = vm_application_service
        self.stream_status_service = stream_status_service
        self.monitoring_service = monitoring_service
        self.webhook_service = webhook_service
        self.auth_service = auth_service

    async def stream_provider(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if not await self._authorize(websocket):
            return
        logger.info("Provider live stream opened")
        try:
            await self._send(
                websocket,
                "hello",
                data={
                    "protocol": "provider-live.v1",
                    "capabilities": {
                        "scopes": list(PROVIDER_LIVE_SCOPES),
                        "client_events": ["refresh", "ping"],
                    },
                    "server_time": self._now(),
                },
            )
            await self._send_snapshot(websocket)
            async with self.broadcaster.subscribe() as queue:
                tasks = [
                    asyncio.create_task(
                        self._receive_loop(websocket), name="provider-live-recv"
                    ),
                    asyncio.create_task(
                        self._invalidation_loop(websocket, queue),
                        name="provider-live-invalidations",
                    ),
                    asyncio.create_task(
                        self._poll_loop(websocket), name="provider-live-reconcile"
                    ),
                    asyncio.create_task(
                        self._heartbeat_loop(websocket), name="provider-live-heartbeat"
                    ),
                ]
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exc = _task_exception(task)
                    if exc and not _is_websocket_disconnect(exc):
                        logger.debug(
                            "Provider live task ended",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )
                    if _is_websocket_disconnect(exc):
                        break
        except WebSocketDisconnect:
            logger.debug("Provider live stream disconnected")
        finally:
            logger.info("Provider live stream closed")

    async def _authorize(self, websocket: WebSocket) -> bool:
        try:
            message = await asyncio.wait_for(
                websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS
            )
            if str(message.get("type") or "") != "auth":
                raise ValidationError("provider live auth message required")
            token = str(message.get("token") or "")
            self.auth_service.validate_admin_token(token)
            return True
        except (AuthError, ValidationError, asyncio.TimeoutError) as exc:
            await self._send(websocket, "error", error=str(exc))
            await websocket.close(code=AUTH_CLOSE_CODE)
            return False

    async def _receive_loop(self, websocket: WebSocket) -> None:
        while True:
            message = await websocket.receive_json()
            event_type = str(message.get("type") or "")
            if event_type == "ping":
                await self._send(
                    websocket, "heartbeat", data={"server_time": self._now()}
                )
            elif event_type == "refresh":
                scopes = self._normalize_scopes(message.get("scopes"))
                await self._refresh_scopes(websocket, scopes)
            else:
                logger.warning(
                    "Unsupported provider live event",
                    extra={"event_type": event_type},
                )
                await self._send(
                    websocket,
                    "error",
                    error=f"unsupported live event: {event_type or 'unknown'}",
                )

    async def _invalidation_loop(
        self, websocket: WebSocket, queue: asyncio.Queue[set[str]]
    ) -> None:
        while True:
            scopes = await queue.get()
            await self._refresh_scopes(websocket, sorted(scopes))

    async def _poll_loop(self, websocket: WebSocket) -> None:
        previous: dict[str, str] = {}
        while True:
            await asyncio.sleep(2)
            for scope in PROVIDER_LIVE_SCOPES:
                try:
                    data = await self._scope_data(scope)
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

    async def _send_snapshot(self, websocket: WebSocket) -> None:
        await self._send(websocket, "snapshot", data=await self._snapshot())

    async def _snapshot(self) -> dict[str, Any]:
        data: dict[str, Any] = {"errors": {}}
        for scope in PROVIDER_LIVE_SCOPES:
            try:
                data.update(self._dashboard_patch(scope, await self._scope_data(scope)))
            except Exception as exc:
                data["errors"][scope] = str(exc)
        return data

    async def _refresh_scopes(self, websocket: WebSocket, scopes: list[str]) -> None:
        for scope in scopes:
            if scope not in PROVIDER_LIVE_SCOPES:
                await self._send(
                    websocket, "error", error=f"unsupported scope: {scope}"
                )
                continue
            try:
                await self._send_update(websocket, scope, await self._scope_data(scope))
            except Exception as exc:
                await self._send_error(websocket, scope, exc)

    async def _scope_data(self, scope: str) -> Any:
        if scope == "provider_info":
            return self.provider_info_service.get_info().model_dump(mode="json")
        if scope == "summary":
            return (await self.summary_service.get_summary()).model_dump(mode="json")
        if scope == "vms":
            return [
                vm.model_dump(mode="json")
                for vm in await self.vm_application_service.list_vms()
            ]
        if scope == "streams":
            return [
                stream.model_dump(mode="json")
                for stream in await self.stream_status_service.list_stream_statuses()
            ]
        if scope == "monitoring":
            return (await self.monitoring_service.overview()).model_dump(mode="json")
        if scope == "metrics":
            history = self.monitoring_service.history(
                scope=MetricScope.HOST,
                range_name="1h",
            ).model_dump(mode="json")
            return {
                "latestMetrics": self.monitoring_service.latest().model_dump(
                    mode="json"
                ),
                "hostCpuHistory": history,
                "hostMemoryHistory": history,
            }
        if scope == "alerts":
            return self.monitoring_service.active_alerts()
        if scope == "alert_rules":
            return [
                rule.model_dump(mode="json")
                for rule in self.monitoring_service.list_alert_rules()
            ]
        if scope == "webhooks":
            if self.webhook_service is not None:
                return [
                    webhook.model_dump(mode="json")
                    for webhook in self.webhook_service.list_webhooks()
                ]
            return [
                webhook.model_dump(mode="json")
                for webhook in self.monitoring_service.list_webhooks()
            ]
        raise ValueError(f"unsupported scope: {scope}")

    def _dashboard_patch(self, scope: str, data: Any) -> dict[str, Any]:
        if scope == "provider_info":
            return {"info": data}
        if scope == "summary":
            return {"summary": data}
        if scope == "vms":
            return {"vms": data}
        if scope == "streams":
            return {"streams": data}
        if scope == "monitoring":
            return {"monitoring": data}
        if scope == "metrics":
            return dict(data)
        if scope == "alerts":
            return {"alerts": data}
        if scope == "alert_rules":
            return {"alertRules": data}
        if scope == "webhooks":
            return {"webhooks": data}
        return {}

    async def _send_update(self, websocket: WebSocket, scope: str, data: Any) -> None:
        await self._send(
            websocket,
            "update",
            scope=scope,
            data=self._dashboard_patch(scope, data),
        )

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
        data: Any = None,
        error: str | None = None,
    ) -> None:
        try:
            await websocket.send_json(
                jsonable_encoder(
                    {
                        "type": event_type,
                        "generated_at": self._now(),
                        "scope": scope,
                        "data": data,
                        "error": error,
                    }
                )
            )
        except Exception as exc:
            if _is_websocket_disconnect(exc):
                raise WebSocketDisconnect() from exc
            raise

    @staticmethod
    def _normalize_scopes(scopes: Any) -> list[str]:
        if not scopes:
            return list(PROVIDER_LIVE_SCOPES)
        return [str(scope) for scope in scopes]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


class HostLiveService:
    """Build and stream the live read model for host monitoring."""

    def __init__(self, monitoring_service: Any, auth_service: Any):
        self.monitoring_service = monitoring_service
        self.auth_service = auth_service

    async def stream_host(
        self,
        websocket: WebSocket,
        history_range: str = "1h",
    ) -> None:
        await websocket.accept()
        if not await self._authorize(websocket):
            return
        try:
            history_range = _validate_history_range(history_range)
        except ValidationError as exc:
            await self._send(websocket, "error", scope="metrics", error=str(exc))
            await websocket.close(code=HISTORY_RANGE_CLOSE_CODE)
            return
        logger.info("Host live stream opened", extra={"history_range": history_range})
        try:
            await self._send(
                websocket,
                "hello",
                data={
                    "protocol": "provider-host-live.v1",
                    "capabilities": {
                        "scopes": ["metrics"],
                        "client_events": ["set_history_range", "refresh", "ping"],
                    },
                    "server_time": self._now(),
                    "sample_interval_seconds": (
                        self.monitoring_service.live_sample_interval_seconds()
                    ),
                },
            )
            await self._send_snapshot(websocket, history_range)
            async with self.monitoring_service.subscribe_host_metrics() as queue:
                tasks = [
                    asyncio.create_task(
                        self._receive_loop(websocket, history_range),
                        name="host-live-recv",
                    ),
                    asyncio.create_task(
                        self._metrics_loop(websocket, queue),
                        name="host-live-metrics",
                    ),
                    asyncio.create_task(
                        self._heartbeat_loop(websocket),
                        name="host-live-heartbeat",
                    ),
                ]
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exc = _task_exception(task)
                    if exc and not _is_websocket_disconnect(exc):
                        logger.debug(
                            "Host live task ended",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )
                    if _is_websocket_disconnect(exc):
                        break
        except WebSocketDisconnect:
            logger.debug("Host live stream disconnected")
        finally:
            logger.info("Host live stream closed")

    async def _authorize(self, websocket: WebSocket) -> bool:
        try:
            message = await asyncio.wait_for(
                websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS
            )
            if str(message.get("type") or "") != "auth":
                raise ValidationError("host live auth message required")
            token = str(message.get("token") or "")
            self.auth_service.validate_admin_token(token)
            return True
        except (AuthError, ValidationError, asyncio.TimeoutError) as exc:
            await self._send(websocket, "error", error=str(exc))
            await websocket.close(code=AUTH_CLOSE_CODE)
            return False

    async def _receive_loop(self, websocket: WebSocket, history_range: str) -> None:
        current_range = history_range
        while True:
            message = await websocket.receive_json()
            event_type = str(message.get("type") or "")
            if event_type == "ping":
                await self._send(
                    websocket, "heartbeat", data={"server_time": self._now()}
                )
            elif event_type == "set_history_range":
                try:
                    current_range = _validate_history_range(
                        str(message.get("history_range") or current_range)
                    )
                except ValidationError as exc:
                    await self._send(
                        websocket, "error", scope="metrics", error=str(exc)
                    )
                    continue
                await self._send_update(
                    websocket, "metrics", await self._metrics_payload(current_range)
                )
            elif event_type == "refresh":
                scopes = message.get("scopes") or ["metrics"]
                if "metrics" in {str(scope) for scope in scopes}:
                    await self._send_update(
                        websocket,
                        "metrics",
                        await self._metrics_payload(current_range),
                    )
            else:
                logger.warning(
                    "Unsupported host live event", extra={"event_type": event_type}
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

    async def _heartbeat_loop(self, websocket: WebSocket) -> None:
        while True:
            await asyncio.sleep(15)
            await self._send(websocket, "heartbeat", data={"server_time": self._now()})

    async def _send_snapshot(self, websocket: WebSocket, history_range: str) -> None:
        await self._send(
            websocket,
            "snapshot",
            data=await self._metrics_payload(history_range),
        )

    async def _metrics_payload(self, history_range: str) -> dict[str, Any]:
        last_sample_at = self.monitoring_service.latest_sample_at()
        return {
            "metrics_latest": self.monitoring_service.latest().model_dump(mode="json"),
            "metrics_history": self.monitoring_service.history(
                scope=MetricScope.HOST,
                range_name=history_range,
            ).model_dump(mode="json"),
            "status": self.monitoring_service.status(),
            "last_sample_at": ensure_utc(last_sample_at).isoformat()
            if last_sample_at
            else None,
        }

    async def _send_update(
        self,
        websocket: WebSocket,
        scope: str,
        data: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> None:
        await self._send(websocket, "update", scope=scope, data=data)

    async def _send(
        self,
        websocket: WebSocket,
        event_type: str,
        *,
        scope: str | None = None,
        data: dict[str, Any] | list[Any] | None = None,
        error: str | None = None,
    ) -> None:
        try:
            await websocket.send_json(
                {
                    "type": event_type,
                    "generated_at": self._now(),
                    "scope": scope,
                    "data": data,
                    "error": error,
                }
            )
        except Exception as exc:
            if _is_websocket_disconnect(exc):
                raise WebSocketDisconnect() from exc
            raise

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
