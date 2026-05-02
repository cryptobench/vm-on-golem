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
    raw: dict[str, Any] | None = None
