from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from provider.utils.time import ensure_utc, utc_now
from provider.webhooks.domain import WebhookConfig, WebhookTestResponse


class MetricSource(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    GUEST_AGENT = "guest_agent"


class MetricScope(str, Enum):
    HOST = "host"
    VM = "vm"


class MetricHistoryRange(str, Enum):
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWENTY_FOUR_HOURS = "24h"
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


class MetricSample(BaseModel):
    scope: MetricScope
    source: MetricSource
    metric: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=utc_now)
    vm_id: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def ensure_timestamp_timezone(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MetricHistoryPoint(BaseModel):
    scope: MetricScope
    source: MetricSource
    vm_id: Optional[str] = None
    metric: str
    unit: str
    bucket_start: datetime
    bucket_end: datetime
    avg: float
    min: float
    max: float
    count: int

    @field_validator("bucket_start", "bucket_end")
    @classmethod
    def ensure_bucket_timezone(cls, value: datetime) -> datetime:
        return ensure_utc(value)


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

    @field_validator("timestamp")
    @classmethod
    def require_explicit_timestamp_timezone(
        cls, value: Optional[datetime]
    ) -> Optional[datetime]:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("timestamp must include an explicit timezone")
        return ensure_utc(value)


class GuestMetricAccepted(BaseModel):
    status: str = "accepted"
    next_interval_seconds: int
    live_mode: bool


class MetricsLatestResponse(BaseModel):
    host: dict[str, Any]
    vms: dict[str, dict[str, Any]]
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def ensure_generated_at_timezone(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MetricsHistoryResponse(BaseModel):
    points: list[MetricHistoryPoint]
    range: MetricHistoryRange
    resolution_seconds: int
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def ensure_history_generated_at_timezone(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MonitoringOverview(BaseModel):
    status: str
    host: dict[str, Any]
    vms: list[dict[str, Any]]
    active_alerts: list[dict[str, Any]]
    last_sample_at: Optional[datetime] = None

    @field_validator("last_sample_at")
    @classmethod
    def ensure_last_sample_at_timezone(
        cls, value: Optional[datetime]
    ) -> Optional[datetime]:
        return ensure_utc(value) if value is not None else value


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
