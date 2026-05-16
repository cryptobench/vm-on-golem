import asyncio
import logging
import ntpath
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import aiohttp
import psutil

from provider.auth.errors import UnauthorizedError
from provider.errors import ValidationError
from provider.utils.time import ensure_utc, utc_now
from provider.webhooks.domain import WebhookEvent, WebhookResource

from .domain import (
    AlertRule,
    GuestMetricAccepted,
    GuestMetricPayload,
    MetricHistoryRange,
    MetricSample,
    MetricScope,
    MetricsHistoryResponse,
    MetricsLatestResponse,
    MetricSource,
    MonitoringOverview,
    WebhookConfig,
    WebhookTestResponse,
)
from .repo import MonitoringRepository

logger = logging.getLogger(__name__)


class MonitoringService:
    """Collect, store, and expose provider monitoring data."""

    def __init__(
        self,
        settings: Any,
        repo: MonitoringRepository,
        vm_service: Any,
        proxy_manager: Any,
        webhook_service: Any = None,
    ):
        self.settings = settings
        self.repo = repo
        self.vm_service = vm_service
        self.proxy_manager = proxy_manager
        self.webhook_service = webhook_service
        self._task: Optional[asyncio.Task] = None
        self._host_live_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._host_live_latest: dict[str, MetricSample] = {}
        self._host_live_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._live_latest: dict[tuple[str, str, str, str], MetricSample] = {}
        self._live_subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._active_watchers: dict[str, int] = {}
        self._last_disconnect: dict[str, datetime] = {}
        self._last_persisted_host_sample: Optional[datetime] = None
        self._last_persisted_guest_sample: dict[str, datetime] = {}

    async def start(self) -> None:
        if not self._setting("MONITORING_ENABLED", True):
            logger.info("Monitoring disabled")
            return
        self.repo.init_schema()
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="monitoring")
        logger.info("Monitoring background loop started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._host_live_task:
            self._host_live_task.cancel()
            try:
                await self._host_live_task
            except asyncio.CancelledError:
                pass
            self._host_live_task = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring background loop stopped")

    def issue_guest_token(self, vm_id: str) -> str:
        self.repo.init_schema()
        return self.repo.issue_guest_token(vm_id)

    def delete_guest_token(self, vm_id: str) -> None:
        self.repo.delete_guest_token(vm_id)

    async def record_guest_sample(
        self, vm_id: str, payload: GuestMetricPayload
    ) -> GuestMetricAccepted:
        self.repo.init_schema()
        if not self.repo.validate_guest_token(vm_id, payload.token):
            raise UnauthorizedError("invalid guest metrics token")

        timestamp = ensure_utc(payload.timestamp) if payload.timestamp else utc_now()
        samples: list[MetricSample] = [
            MetricSample(
                scope=MetricScope.VM,
                source=MetricSource.GUEST_AGENT,
                vm_id=vm_id,
                metric="agent_heartbeat",
                value=1,
                unit="count",
                timestamp=timestamp,
            )
        ]
        metrics = {
            "cpu_percent": (payload.cpu_percent, "percent"),
            "memory_used_bytes": (payload.memory_used_bytes, "bytes"),
            "memory_total_bytes": (payload.memory_total_bytes, "bytes"),
            "disk_used_bytes": (payload.disk_used_bytes, "bytes"),
            "disk_total_bytes": (payload.disk_total_bytes, "bytes"),
            "load_1m": (payload.load_1m, "count"),
            "network_rx_bytes": (payload.network_rx_bytes, "bytes"),
            "network_tx_bytes": (payload.network_tx_bytes, "bytes"),
        }
        for metric, (value, unit) in metrics.items():
            if value is not None:
                samples.append(
                    MetricSample(
                        scope=MetricScope.VM,
                        source=MetricSource.GUEST_AGENT,
                        vm_id=vm_id,
                        metric=metric,
                        value=float(value),
                        unit=unit,
                        timestamp=timestamp,
                    )
                )

        if payload.memory_used_bytes is not None and payload.memory_total_bytes:
            samples.append(
                MetricSample(
                    scope=MetricScope.VM,
                    source=MetricSource.GUEST_AGENT,
                    vm_id=vm_id,
                    metric="memory_percent",
                    value=(payload.memory_used_bytes / payload.memory_total_bytes)
                    * 100,
                    unit="percent",
                    timestamp=timestamp,
                )
            )
        if payload.disk_used_bytes is not None and payload.disk_total_bytes:
            samples.append(
                MetricSample(
                    scope=MetricScope.VM,
                    source=MetricSource.GUEST_AGENT,
                    vm_id=vm_id,
                    metric="disk_percent",
                    value=(payload.disk_used_bytes / payload.disk_total_bytes) * 100,
                    unit="percent",
                    timestamp=timestamp,
                )
            )

        self._cache_live_samples(samples)
        should_persist = self._should_persist_guest_samples(vm_id, timestamp)
        if should_persist:
            self.repo.add_samples(samples)
            self._last_persisted_guest_sample[vm_id] = timestamp
            await self._evaluate_alerts()
        await self._publish_vm_metrics(vm_id, samples)
        return GuestMetricAccepted(
            next_interval_seconds=self.guest_sample_interval(vm_id),
            live_mode=self.is_vm_live(vm_id),
        )

    async def overview(self) -> MonitoringOverview:
        latest = self._latest_by_scope()
        vms = await self._vm_overview(latest)
        host = latest.get("host", {})
        return MonitoringOverview(
            status=self.status(),
            host=host,
            vms=vms,
            active_alerts=self.repo.active_alerts(),
            last_sample_at=self.latest_sample_at(),
        )

    def latest(self) -> MetricsLatestResponse:
        latest = self._latest_by_scope()
        return MetricsLatestResponse(
            host=latest.get("host", {}),
            vms=latest.get("vms", {}),
            generated_at=utc_now(),
        )

    def latest_for_vm(self, vm_id: str) -> MetricsLatestResponse:
        latest = self.latest()
        latest.vms = {vm_id: latest.vms.get(vm_id, {})}
        return latest

    def status(self) -> str:
        return "healthy" if not self.repo.active_alerts() else "issues"

    def latest_sample_at(self) -> Optional[datetime]:
        return self._latest_timestamp()

    def live_sample_interval_seconds(self) -> int:
        return int(self._setting("MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS", 1))

    def history(
        self,
        scope: MetricScope,
        range_name: str | MetricHistoryRange,
        vm_id: Optional[str] = None,
        source: Optional[MetricSource] = None,
    ) -> MetricsHistoryResponse:
        history_range = self._validate_history_range(range_name)
        resolution_seconds = self._history_resolution_seconds(history_range)
        since = utc_now() - self._range_delta(history_range)
        return MetricsHistoryResponse(
            points=self.repo.history_points(
                scope=scope,
                since=since,
                resolution_seconds=resolution_seconds,
                vm_id=vm_id,
                source=source,
            ),
            range=history_range,
            resolution_seconds=resolution_seconds,
            generated_at=utc_now(),
        )

    def is_vm_live(self, vm_id: str) -> bool:
        if self._active_watchers.get(vm_id, 0) > 0:
            return True
        disconnected_at = self._last_disconnect.get(vm_id)
        if disconnected_at is None:
            return False
        grace = int(self._setting("MONITORING_LIVE_DISCONNECT_GRACE_SECONDS", 60))
        return utc_now() - disconnected_at <= timedelta(seconds=grace)

    def guest_sample_interval(self, vm_id: str) -> int:
        if self.is_vm_live(vm_id):
            return int(self._setting("MONITORING_LIVE_ACTIVE_INTERVAL_SECONDS", 1))
        return int(
            self._setting(
                "MONITORING_LIVE_IDLE_INTERVAL_SECONDS",
                self._setting("MONITORING_SAMPLE_INTERVAL_SECONDS", 30),
            )
        )

    @asynccontextmanager
    async def watch_vm(self, vm_id: str):
        self._active_watchers[vm_id] = self._active_watchers.get(vm_id, 0) + 1
        logger.debug(
            "VM live watcher connected",
            extra={"vm_id": vm_id, "watchers": self._active_watchers[vm_id]},
        )
        try:
            yield
        finally:
            current = self._active_watchers.get(vm_id, 0) - 1
            if current > 0:
                self._active_watchers[vm_id] = current
            else:
                self._active_watchers.pop(vm_id, None)
                self._last_disconnect[vm_id] = utc_now()
            logger.debug(
                "VM live watcher disconnected",
                extra={"vm_id": vm_id, "watchers": self._active_watchers.get(vm_id, 0)},
            )

    @asynccontextmanager
    async def subscribe_host_metrics(self):
        self.repo.init_schema()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=16)
        self._host_live_subscribers.add(queue)
        logger.debug(
            "Host metrics subscriber connected",
            extra={"subscribers": len(self._host_live_subscribers)},
        )
        self._ensure_host_live_task()
        try:
            yield queue
        finally:
            self._host_live_subscribers.discard(queue)
            if not self._host_live_subscribers and self._host_live_task:
                task = self._host_live_task
                task.cancel()
                self._host_live_task = None
                await asyncio.gather(task, return_exceptions=True)
            logger.debug(
                "Host metrics subscriber disconnected",
                extra={"subscribers": len(self._host_live_subscribers)},
            )

    @asynccontextmanager
    async def subscribe_vm_metrics(self, vm_id: str):
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=16)
        subscribers = self._live_subscribers.setdefault(vm_id, set())
        subscribers.add(queue)
        logger.debug(
            "VM metrics subscriber connected",
            extra={"vm_id": vm_id, "subscribers": len(subscribers)},
        )
        try:
            yield queue
        finally:
            subscribers.discard(queue)
            if not subscribers:
                self._live_subscribers.pop(vm_id, None)
            logger.debug(
                "VM metrics subscriber disconnected",
                extra={"vm_id": vm_id, "subscribers": len(subscribers)},
            )

    def list_alert_rules(self) -> list[AlertRule]:
        return self.repo.list_alert_rules()

    def create_alert_rule(self, rule: AlertRule) -> AlertRule:
        return self.repo.create_alert_rule(rule)

    def active_alerts(self) -> list[dict[str, Any]]:
        return self.repo.active_alerts()

    def list_webhooks(self) -> list[WebhookConfig]:
        if self.webhook_service is not None:
            return self.webhook_service.list_webhooks()
        return self.repo.list_webhooks()

    def create_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        if self.webhook_service is not None:
            return self.webhook_service.create_webhook(webhook)
        return self.repo.create_webhook(webhook)

    async def test_webhook(self, webhook_id: int) -> WebhookTestResponse:
        if self.webhook_service is not None:
            return await self.webhook_service.test_webhook(webhook_id)
        webhook = next(
            (item for item in self.repo.list_webhooks() if item.id == webhook_id), None
        )
        if webhook is None:
            raise ValueError("webhook not found")
        status, error = await self._post_webhook(
            webhook,
            {
                "event": "webhook.test",
                "sent_at": utc_now().isoformat(),
                "provider_id": self._setting("PROVIDER_ID", ""),
            },
        )
        return WebhookTestResponse(ok=error is None, status=status, error=error)

    async def prometheus_metrics(self) -> str:
        lines = [
            "# HELP golem_monitoring_sample Latest monitoring sample value.",
            "# TYPE golem_monitoring_sample gauge",
        ]
        for sample in self.repo.latest_samples():
            labels = {
                "scope": sample.scope.value,
                "source": sample.source.value,
                "metric": sample.metric,
            }
            if sample.vm_id:
                labels["vm_id"] = sample.vm_id
            label_text = ",".join(f'{key}="{value}"' for key, value in labels.items())
            lines.append(f"golem_monitoring_sample{{{label_text}}} {sample.value}")
        lines.append("# HELP golem_monitoring_alert_active Active monitoring alerts.")
        lines.append("# TYPE golem_monitoring_alert_active gauge")
        for alert in self.repo.active_alerts():
            vm_label = alert.get("vm_id") or ""
            lines.append(
                'golem_monitoring_alert_active{rule="%s",severity="%s",vm_id="%s"} 1'
                % (alert.get("name", ""), alert.get("severity", ""), vm_label)
            )
        return "\n".join(lines) + "\n"

    async def _run_loop(self) -> None:
        interval = int(self._setting("MONITORING_SAMPLE_INTERVAL_SECONDS", 30))
        retention_days = int(self._setting("MONITORING_RETENTION_DAYS", 30))
        while not self._stop_event.is_set():
            try:
                logger.debug("Monitoring collection tick")
                samples = await self._collect_samples()
                self.repo.add_samples(samples)
                self.repo.prune(retention_days)
                await self._evaluate_alerts()
            except Exception:
                logger.error("monitoring collection failed", exc_info=True)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _collect_samples(self) -> list[MetricSample]:
        now = utc_now()
        samples = self._host_samples(now)
        samples.extend(await self._vm_infrastructure_samples(now))
        return samples

    def _ensure_host_live_task(self) -> None:
        if self._host_live_task and not self._host_live_task.done():
            return
        self._host_live_task = asyncio.create_task(
            self._run_host_live_loop(), name="monitoring-host-live"
        )

    async def _run_host_live_loop(self) -> None:
        interval = self.live_sample_interval_seconds()
        while self._host_live_subscribers and not self._stop_event.is_set():
            try:
                await self.record_host_live_sample()
            except Exception:
                logger.error("host live monitoring collection failed", exc_info=True)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def record_host_live_sample(
        self, timestamp: Optional[datetime] = None
    ) -> list[MetricSample]:
        self.repo.init_schema()
        samples = self._host_samples(ensure_utc(timestamp) if timestamp else utc_now())
        self._cache_host_live_samples(samples)
        if self._should_persist_host_samples(samples[0].timestamp):
            self.repo.add_samples(samples)
            self._last_persisted_host_sample = samples[0].timestamp
            await self._evaluate_alerts()
        await self._publish_host_metrics(samples)
        return samples

    def _host_samples(self, now: datetime) -> list[MetricSample]:
        disk = psutil.disk_usage(self._host_disk_path())
        memory = psutil.virtual_memory()
        net = psutil.net_io_counters()
        values = {
            "cpu_percent": (psutil.cpu_percent(interval=None), "percent"),
            "memory_percent": (memory.percent, "percent"),
            "memory_total_bytes": (memory.total, "bytes"),
            "memory_used_bytes": (memory.used, "bytes"),
            "disk_percent": (disk.percent, "percent"),
            "disk_total_bytes": (disk.total, "bytes"),
            "disk_used_bytes": (disk.used, "bytes"),
            "network_rx_bytes": (net.bytes_recv, "bytes"),
            "network_tx_bytes": (net.bytes_sent, "bytes"),
        }
        try:
            load_1m, load_5m, load_15m = psutil.getloadavg()
        except (AttributeError, NotImplementedError, OSError):
            pass
        else:
            values.update(
                {
                    "load_1m": (load_1m, "count"),
                    "load_5m": (load_5m, "count"),
                    "load_15m": (load_15m, "count"),
                }
            )
        return [
            MetricSample(
                scope=MetricScope.HOST,
                source=MetricSource.INFRASTRUCTURE,
                metric=metric,
                value=float(value),
                unit=unit,
                timestamp=now,
            )
            for metric, (value, unit) in values.items()
        ]

    def _host_disk_path(self) -> str:
        configured = str(self._setting("VM_DATA_DIR", "") or "").strip()
        if configured:
            drive, _ = ntpath.splitdrive(configured)
            if drive:
                return f"{drive}\\"
            path = Path(configured).expanduser()
            for candidate in (path, *path.parents):
                if candidate.exists():
                    return str(candidate)
            if path.anchor:
                return path.anchor
        return Path.cwd().anchor or os.sep

    async def _vm_infrastructure_samples(self, now: datetime) -> list[MetricSample]:
        samples: list[MetricSample] = []
        try:
            vms = await self.vm_service.list_vms()
        except Exception:
            logger.warning("failed to list VMs for monitoring", exc_info=True)
            return samples

        traffic = {}
        if hasattr(self.proxy_manager, "get_traffic_counters"):
            traffic = self.proxy_manager.get_traffic_counters()
        latest = self._latest_by_scope().get("vms", {})

        for vm in vms:
            vm_id = vm.id
            counters = traffic.get(vm_id, traffic.get(vm.name, {}))
            values = {
                "allocated_cpu": (vm.resources.cpu, "cores"),
                "allocated_memory_gb": (vm.resources.memory, "gb"),
                "allocated_storage_gb": (vm.resources.storage, "gb"),
                "proxy_rx_bytes": (counters.get("rx_bytes", 0), "bytes"),
                "proxy_tx_bytes": (counters.get("tx_bytes", 0), "bytes"),
                "proxy_connections": (counters.get("connections", 0), "count"),
                "status_running": (
                    1 if str(vm.status.value) == "running" else 0,
                    "bool",
                ),
            }
            guest = latest.get(vm_id, {}).get("guest_agent", {})
            heartbeat = guest.get("agent_heartbeat")
            if heartbeat and heartbeat.get("timestamp"):
                age = (now - heartbeat["timestamp"]).total_seconds()
                values["guest_agent_age_seconds"] = (age, "seconds")
            else:
                values["guest_agent_age_seconds"] = (999999999.0, "seconds")

            samples.extend(
                MetricSample(
                    scope=MetricScope.VM,
                    source=MetricSource.INFRASTRUCTURE,
                    vm_id=vm_id,
                    metric=metric,
                    value=float(value),
                    unit=unit,
                    timestamp=now,
                )
                for metric, (value, unit) in values.items()
            )
        return samples

    async def _evaluate_alerts(self) -> None:
        latest = self.repo.latest_samples()
        rules = [rule for rule in self.repo.list_alert_rules() if rule.enabled]
        latest_by_key = {
            (sample.scope, sample.source, sample.vm_id, sample.metric): sample
            for sample in latest
        }
        fired_payloads = []
        resolved_payloads = []
        for rule in rules:
            candidates = [
                sample
                for key, sample in latest_by_key.items()
                if key[0] == rule.scope
                and key[1] == rule.source
                and key[3] == rule.metric
            ]
            for sample in candidates:
                violates = self._violates(sample.value, rule.operator, rule.threshold)
                sustained = self._sustained(rule, sample.vm_id)
                if violates and sustained:
                    created = self.repo.upsert_active_alert(
                        rule, sample.vm_id, sample.value
                    )
                    if created:
                        fired_payloads.append(
                            self._alert_payload("alert.fired", rule, sample)
                        )
                elif not violates:
                    resolved = self.repo.resolve_alert(rule, sample.vm_id)
                    if resolved:
                        resolved_payloads.append(
                            self._alert_payload("alert.resolved", rule, sample)
                        )
        for payload in [*fired_payloads, *resolved_payloads]:
            if self.webhook_service is not None:
                await self.webhook_service.emit_event(payload)
            else:
                await self._send_webhooks(
                    payload.model_dump(mode="json")
                    if hasattr(payload, "model_dump")
                    else payload
                )

    def _sustained(self, rule: AlertRule, vm_id: Optional[str]) -> bool:
        if rule.duration_seconds <= 0:
            return True
        since = utc_now() - timedelta(seconds=rule.duration_seconds)
        history = self.repo.history(
            scope=rule.scope, source=rule.source, vm_id=vm_id, since=since
        )
        relevant = [sample for sample in history if sample.metric == rule.metric]
        if not relevant:
            return False
        oldest = min(sample.timestamp for sample in relevant)
        return oldest <= since and all(
            self._violates(sample.value, rule.operator, rule.threshold)
            for sample in relevant
        )

    async def _send_webhooks(self, payload: dict[str, Any]) -> None:
        for webhook in self.repo.list_webhooks():
            if not webhook.enabled or webhook.id is None:
                continue
            status, error = await self._post_webhook(webhook, payload)
            self.repo.update_webhook_result(
                webhook.id, str(status) if status else "error", error
            )
            if error is not None:
                logger.warning(
                    "Monitoring webhook delivery failed",
                    extra={"webhook_id": webhook.id, "status": status, "error": error},
                )

    async def _post_webhook(
        self, webhook: WebhookConfig, payload: dict[str, Any]
    ) -> tuple[Optional[int], Optional[str]]:
        timeout = aiohttp.ClientTimeout(
            total=float(self._setting("MONITORING_WEBHOOK_TIMEOUT_SECONDS", 5))
        )
        last_error = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(webhook.url, json=payload) as response:
                        if 200 <= response.status < 300:
                            return response.status, None
                        last_error = await response.text()
                        status = response.status
            except Exception as exc:
                status = None
                last_error = str(exc)
            if attempt < 2:
                await asyncio.sleep(2**attempt)
        return status, last_error

    def _latest_by_scope(self) -> dict[str, Any]:
        result: dict[str, Any] = {"host": {}, "vms": {}}
        for sample in self.repo.latest_samples():
            self._merge_latest_sample(result, sample)
        for sample in self._host_live_latest.values():
            self._merge_latest_sample(result, sample)
        for sample in self._live_latest.values():
            self._merge_latest_sample(result, sample)
        return result

    async def _vm_overview(self, latest: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            vms = await self.vm_service.list_vms()
        except Exception:
            return []
        rows = []
        for vm in vms:
            metrics = latest.get("vms", {}).get(vm.id, {})
            rows.append(
                {
                    "id": vm.id,
                    "status": vm.status.value
                    if hasattr(vm.status, "value")
                    else str(vm.status),
                    "resources": vm.resources.model_dump(),
                    "metrics": metrics,
                }
            )
        return rows

    def _latest_timestamp(self) -> Optional[datetime]:
        samples = [
            *self.repo.latest_samples(),
            *self._host_live_latest.values(),
            *self._live_latest.values(),
        ]
        if not samples:
            return None
        return max(sample.timestamp for sample in samples)

    def _cache_host_live_samples(self, samples: list[MetricSample]) -> None:
        for sample in samples:
            if sample.scope != MetricScope.HOST:
                continue
            self._host_live_latest[sample.metric] = sample

    def _cache_live_samples(self, samples: list[MetricSample]) -> None:
        for sample in samples:
            if sample.vm_id is None:
                continue
            key = (
                sample.scope.value,
                sample.source.value,
                sample.vm_id,
                sample.metric,
            )
            self._live_latest[key] = sample

    def _should_persist_host_samples(self, timestamp: datetime) -> bool:
        interval = int(self._setting("MONITORING_HISTORY_DOWNSAMPLE_SECONDS", 10))
        if self._last_persisted_host_sample is None:
            return True
        return timestamp - self._last_persisted_host_sample >= timedelta(
            seconds=interval
        )

    def _should_persist_guest_samples(self, vm_id: str, timestamp: datetime) -> bool:
        interval = int(self._setting("MONITORING_HISTORY_DOWNSAMPLE_SECONDS", 10))
        previous = self._last_persisted_guest_sample.get(vm_id)
        if previous is None:
            return True
        return timestamp - previous >= timedelta(seconds=interval)

    async def _publish_vm_metrics(
        self, vm_id: str, samples: list[MetricSample]
    ) -> None:
        subscribers = list(self._live_subscribers.get(vm_id, set()))
        if not subscribers:
            return
        payload = {
            "latest": self.latest_for_vm(vm_id).model_dump(mode="json"),
            "samples": [
                sample.model_dump(mode="json")
                for sample in samples
                if sample.scope == MetricScope.VM and sample.vm_id == vm_id
            ],
            "guest_interval_seconds": self.guest_sample_interval(vm_id),
            "live_mode": self.is_vm_live(vm_id),
        }
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(payload)

    async def _publish_host_metrics(self, samples: list[MetricSample]) -> None:
        subscribers = list(self._host_live_subscribers)
        if not subscribers:
            return
        last_sample_at = self.latest_sample_at()
        payload = {
            "latest": self.latest().model_dump(mode="json"),
            "samples": [
                sample.model_dump(mode="json")
                for sample in samples
                if sample.scope == MetricScope.HOST
            ],
            "status": self.status(),
            "last_sample_at": ensure_utc(last_sample_at).isoformat()
            if last_sample_at
            else None,
        }
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(payload)

    @staticmethod
    def _merge_latest_sample(result: dict[str, Any], sample: MetricSample) -> None:
        value = {
            "value": sample.value,
            "unit": sample.unit,
            "timestamp": sample.timestamp,
            "source": sample.source.value,
        }
        if sample.scope == MetricScope.HOST:
            current = result["host"].get(sample.metric)
            if not current or current["timestamp"] <= sample.timestamp:
                result["host"][sample.metric] = value
            return

        vm = result["vms"].setdefault(sample.vm_id or "unknown", {})
        source_bucket = vm.setdefault(sample.source.value, {})
        current = source_bucket.get(sample.metric)
        if not current or current["timestamp"] <= sample.timestamp:
            source_bucket[sample.metric] = value

    @staticmethod
    def _violates(value: float, operator: str, threshold: float) -> bool:
        if value == float("inf"):
            return True
        if operator == ">=":
            return value >= threshold
        if operator == "<":
            return value < threshold
        if operator == "<=":
            return value <= threshold
        return value > threshold

    @staticmethod
    def _validate_history_range(
        range_name: str | MetricHistoryRange,
    ) -> MetricHistoryRange:
        if isinstance(range_name, MetricHistoryRange):
            return range_name
        try:
            return MetricHistoryRange(str(range_name))
        except ValueError as exc:
            supported = ", ".join(MetricHistoryRange.values())
            raise ValidationError(
                f"invalid metrics history range: {range_name}. "
                f"Supported ranges: {supported}"
            ) from exc

    @classmethod
    def _range_delta(cls, range_name: str | MetricHistoryRange) -> timedelta:
        history_range = cls._validate_history_range(range_name)
        ranges = {
            MetricHistoryRange.ONE_HOUR: timedelta(hours=1),
            MetricHistoryRange.SIX_HOURS: timedelta(hours=6),
            MetricHistoryRange.TWENTY_FOUR_HOURS: timedelta(hours=24),
            MetricHistoryRange.SEVEN_DAYS: timedelta(days=7),
            MetricHistoryRange.THIRTY_DAYS: timedelta(days=30),
        }
        return ranges[history_range]

    @classmethod
    def _history_resolution_seconds(cls, range_name: str | MetricHistoryRange) -> int:
        history_range = cls._validate_history_range(range_name)
        resolutions = {
            MetricHistoryRange.ONE_HOUR: 10,
            MetricHistoryRange.SIX_HOURS: 60,
            MetricHistoryRange.TWENTY_FOUR_HOURS: 5 * 60,
            MetricHistoryRange.SEVEN_DAYS: 60 * 60,
            MetricHistoryRange.THIRTY_DAYS: 6 * 60 * 60,
        }
        return resolutions[history_range]

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def _alert_payload(self, event: str, rule: AlertRule, sample: MetricSample) -> Any:
        if self.webhook_service is not None:
            severity = "critical" if rule.severity == "critical" else "warning"
            status = "fired" if event == "alert.fired" else "resolved"
            return WebhookEvent(
                event_type=event,
                provider_id=str(self._setting("PROVIDER_ID", "") or ""),
                resource=WebhookResource(type="alert", id=rule.name),
                severity=severity if event == "alert.fired" else "info",
                summary=f"{rule.name} {status}",
                data={
                    "rule": rule.model_dump(mode="json"),
                    "vm_id": sample.vm_id,
                    "metric": sample.metric,
                    "value": sample.value,
                    "unit": sample.unit,
                    "source": sample.source.value,
                    "scope": sample.scope.value,
                },
            )
        return {
            "event": event,
            "provider_id": self._setting("PROVIDER_ID", ""),
            "rule": rule.model_dump(),
            "vm_id": sample.vm_id,
            "metric": sample.metric,
            "value": sample.value,
            "unit": sample.unit,
            "source": sample.source.value,
            "scope": sample.scope.value,
            "sent_at": utc_now().isoformat(),
        }
