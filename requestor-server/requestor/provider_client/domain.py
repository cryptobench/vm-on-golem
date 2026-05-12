from typing import Any

from pydantic import BaseModel


class ProviderVMCreateCommand(BaseModel):
    name: str
    cpu: int
    memory: int
    storage: int
    ssh_key: str
    stream_id: int | None = None


class ProviderVMJob(BaseModel):
    job_id: str
    vm_id: str
    status: str
    lifecycle_stage: str | None = None
    status_message: str | None = None
    progress: int | None = None
    transitioning: bool | None = None
    next_poll_seconds: int | None = None
    raw: dict[str, Any] | None = None
