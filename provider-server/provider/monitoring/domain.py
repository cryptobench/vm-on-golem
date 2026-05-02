from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MetricSource(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    GUEST_AGENT = "guest_agent"


class MetricScope(str, Enum):
    HOST = "host"
    VM = "vm"


class MetricSample(BaseModel):
    scope: MetricScope
    source: MetricSource
    metric: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    vm_id: Optional[str] = None


class GuestMetricPayload(BaseModel):
    token: str
    cpu_percent: Optional[float] = None
    memory_used_bytes: Optional[float] = None
    memory_total_bytes: Optional[float] = None
    disk_used_bytes: Optional[float] = None
    disk_total_bytes: Optional[float] = None
    load_1m: Optional[float] = None
    network_rx_bytes: Optional[float] = None
    network_tx_bytes: Optional[float] = None
    agent_version: str = "unknown"
    timestamp: Optional[datetime] = None


class MetricsLatestResponse(BaseModel):
    host: dict[str, Any]
    vms: dict[str, dict[str, Any]]
    generated_at: datetime


class MetricsHistoryResponse(BaseModel):
    samples: list[MetricSample]


class MonitoringOverview(BaseModel):
    status: str
    host: dict[str, Any]
    vms: list[dict[str, Any]]
    active_alerts: list[dict[str, Any]]
    last_sample_at: Optional[datetime] = None


class AlertRule(BaseModel):
    id: Optional[int] = None
    name: str
    metric: str
    scope: MetricScope
    source: MetricSource
    operator: str = ">"
    threshold: float
    duration_seconds: int = 300
    severity: str = "warning"
    enabled: bool = True


class WebhookConfig(BaseModel):
    id: Optional[int] = None
    name: str
    url: str
    enabled: bool = True
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    last_delivered_at: Optional[datetime] = None


class WebhookTestResponse(BaseModel):
    ok: bool
    status: Optional[int] = None
    error: Optional[str] = None
