from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from provider.utils.time import ensure_utc, utc_now

WebhookEventType = Literal[
    "alert.fired",
    "alert.resolved",
    "vm.ready",
    "vm.failed",
    "vm.stopped",
    "vm.deleted",
    "payment.stream.lost",
]

WebhookServiceType = Literal["generic_json", "discord", "slack"]
WebhookDeliveryStatus = Literal["pending", "success", "failed"]
WebhookSeverity = Literal["info", "warning", "critical"]

WEBHOOK_EVENT_TYPES: tuple[str, ...] = (
    "alert.fired",
    "alert.resolved",
    "vm.ready",
    "vm.failed",
    "vm.stopped",
    "vm.deleted",
    "payment.stream.lost",
)


class WebhookTemplateField(BaseModel):
    name: str
    value: str


class WebhookTemplate(BaseModel):
    title: str = "{{summary}}"
    message: str = "{{summary}}"
    color: str = "severity"
    fields: list[WebhookTemplateField] = Field(
        default_factory=lambda: [
            WebhookTemplateField(name="Event", value="{{event.type}}"),
            WebhookTemplateField(name="Resource", value="{{resource.id}}"),
            WebhookTemplateField(name="Severity", value="{{severity}}"),
        ]
    )
    footer: str = "Golem Provider"


class WebhookResource(BaseModel):
    type: str
    id: str


class WebhookEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: WebhookEventType
    created_at: datetime = Field(default_factory=utc_now)
    provider_id: str
    resource: WebhookResource
    severity: WebhookSeverity = "info"
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def ensure_created_at_timezone(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class WebhookConfig(BaseModel):
    id: Optional[int] = None
    name: str
    url: str
    enabled: bool = True
    service_type: WebhookServiceType = "generic_json"
    events: list[WebhookEventType] = Field(
        default_factory=lambda: list(WEBHOOK_EVENT_TYPES)
    )
    template: WebhookTemplate = Field(default_factory=WebhookTemplate)
    last_status: Optional[WebhookDeliveryStatus] = None
    last_http_status: Optional[int] = None
    last_error: Optional[str] = None
    last_delivered_at: Optional[datetime] = None

    @field_validator("events")
    @classmethod
    def require_events(cls, value: list[WebhookEventType]) -> list[WebhookEventType]:
        if not value:
            raise ValueError("at least one webhook event is required")
        return value

    @field_validator("last_delivered_at")
    @classmethod
    def ensure_last_delivered_at_timezone(
        cls, value: Optional[datetime]
    ) -> Optional[datetime]:
        return ensure_utc(value) if value is not None else value


class WebhookDeliveryAttempt(BaseModel):
    id: Optional[int] = None
    webhook_id: int
    event_id: str
    event_type: str
    attempt: int
    status: WebhookDeliveryStatus
    http_status: Optional[int] = None
    error: Optional[str] = None
    attempted_at: datetime = Field(default_factory=utc_now)

    @field_validator("attempted_at")
    @classmethod
    def ensure_attempted_at_timezone(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class WebhookPreviewRequest(BaseModel):
    service_type: WebhookServiceType
    template: WebhookTemplate = Field(default_factory=WebhookTemplate)
    event_type: WebhookEventType = "alert.fired"


class WebhookPreviewResponse(BaseModel):
    service_type: WebhookServiceType
    payload: dict[str, Any]


class WebhookTestRequest(BaseModel):
    event_type: WebhookEventType = "alert.fired"


class WebhookTestResponse(BaseModel):
    ok: bool
    status: Optional[int] = None
    error: Optional[str] = None
    event_id: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
