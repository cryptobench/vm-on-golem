import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import aiohttp
import psutil

from .domain import (
    AlertRule,
    GuestMetricPayload,
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
    ):
        self.settings = settings
        self.repo = repo
        self.vm_service = vm_service
        self.proxy_manager = proxy_manager
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not self._setting("MONITORING_ENABLED", True):
            logger.info("Monitoring disabled")
            return
        self.repo.init_schema()
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="monitoring")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def issue_guest_token(self, vm_id: str) -> str:
        self.repo.init_schema()
        return self.repo.issue_guest_token(vm_id)

    def delete_guest_token(self, vm_id: str) -> None:
        self.repo.delete_guest_token(vm_id)

    async def record_guest_sample(
        self, vm_id: str, payload: GuestMetricPayload
    ) -> dict[str, str]:
        self.repo.init_schema()
        if not self.repo.validate_guest_token(vm_id, payload.token):
            raise ValueError("invalid guest metrics token")

        timestamp = payload.timestamp or datetime.utcnow()
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

        self.repo.add_samples(samples)
        await self._evaluate_alerts()
        return {"status": "accepted"}

    async def overview(self) -> MonitoringOverview:
        latest = self._latest_by_scope()
        vms = await self._vm_overview(latest)
        host = latest.get("host", {})
        last_sample_at = self._latest_timestamp()
        return MonitoringOverview(
            status="healthy" if not self.repo.active_alerts() else "issues",
            host=host,
            vms=vms,
            active_alerts=self.repo.active_alerts(),
            last_sample_at=last_sample_at,
        )

    def latest(self) -> MetricsLatestResponse:
        latest = self._latest_by_scope()
        return MetricsLatestResponse(
            host=latest.get("host", {}),
            vms=latest.get("vms", {}),
            generated_at=datetime.utcnow(),
        )

    def history(
        self,
        scope: MetricScope,
        range_name: str,
        vm_id: Optional[str] = None,
        source: Optional[MetricSource] = None,
    ) -> MetricsHistoryResponse:
        since = datetime.utcnow() - self._range_delta(range_name)
        return MetricsHistoryResponse(
            samples=self.repo.history(
                scope=scope, since=since, vm_id=vm_id, source=source
            )
        )

    def list_alert_rules(self) -> list[AlertRule]:
        return self.repo.list_alert_rules()

    def create_alert_rule(self, rule: AlertRule) -> AlertRule:
        return self.repo.create_alert_rule(rule)

    def active_alerts(self) -> list[dict[str, Any]]:
        return self.repo.active_alerts()

    def list_webhooks(self) -> list[WebhookConfig]:
        return self.repo.list_webhooks()

    def create_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        return self.repo.create_webhook(webhook)

    async def test_webhook(self, webhook_id: int) -> WebhookTestResponse:
        webhook = next(
            (item for item in self.repo.list_webhooks() if item.id == webhook_id), None
        )
        if webhook is None:
            raise ValueError("webhook not found")
        status, error = await self._post_webhook(
            webhook,
            {
                "event": "webhook.test",
                "sent_at": datetime.utcnow().isoformat(),
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
        now = datetime.utcnow()
        samples = self._host_samples(now)
        samples.extend(await self._vm_infrastructure_samples(now))
        return samples

    def _host_samples(self, now: datetime) -> list[MetricSample]:
        disk = psutil.disk_usage("/")
        memory = psutil.virtual_memory()
        net = psutil.net_io_counters()
        load_1m, load_5m, load_15m = psutil.getloadavg()
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
            "load_1m": (load_1m, "count"),
            "load_5m": (load_5m, "count"),
            "load_15m": (load_15m, "count"),
        }
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
            await self._send_webhooks(payload)

    def _sustained(self, rule: AlertRule, vm_id: Optional[str]) -> bool:
        if rule.duration_seconds <= 0:
            return True
        since = datetime.utcnow() - timedelta(seconds=rule.duration_seconds)
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
            value = {
                "value": sample.value,
                "unit": sample.unit,
                "timestamp": sample.timestamp,
                "source": sample.source.value,
            }
            if sample.scope == MetricScope.HOST:
                result["host"][sample.metric] = value
            else:
                vm = result["vms"].setdefault(sample.vm_id or "unknown", {})
                source_bucket = vm.setdefault(sample.source.value, {})
                source_bucket[sample.metric] = value
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
        samples = self.repo.latest_samples()
        if not samples:
            return None
        return max(sample.timestamp for sample in samples)

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
    def _range_delta(range_name: str) -> timedelta:
        ranges = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        return ranges.get(range_name, ranges["1h"])

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def _alert_payload(
        self, event: str, rule: AlertRule, sample: MetricSample
    ) -> dict[str, Any]:
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
            "sent_at": datetime.utcnow().isoformat(),
        }
