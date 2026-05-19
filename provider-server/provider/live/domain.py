from typing import Any, Literal

from pydantic import BaseModel, Field

LiveScope = Literal[
    "provider_info",
    "lifecycle",
    "access",
    "job",
    "snapshots",
    "stream",
    "metrics_live",
    "metrics_history",
]


class LiveEvent(BaseModel):
    type: Literal["hello", "snapshot", "update", "error", "heartbeat"]
    generated_at: str
    scope: LiveScope | None = None
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class LiveSnapshot(BaseModel):
    provider_info: dict[str, Any] | None = None
    lifecycle: dict[str, Any] | None = None
    access: dict[str, Any] | None = None
    job: dict[str, Any] | None = None
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    stream: dict[str, Any] | None = None
    metrics_live: dict[str, Any] | None = None
    metrics_history: dict[str, Any] | None = None
    errors: dict[str, str] = Field(default_factory=dict)
