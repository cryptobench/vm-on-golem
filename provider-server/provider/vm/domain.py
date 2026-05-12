from pydantic import BaseModel

from .models import VMResources


class CreateVMCommand(BaseModel):
    name: str
    image: str
    resources: VMResources
    ssh_key: str
    stream_id: int | None = None
    async_mode: bool = False


class CreateVMJobResult(BaseModel):
    job_id: str
    vm_id: str
    status: str
    lifecycle_stage: str
    status_message: str
    progress: int
    transitioning: bool = True
    next_poll_seconds: int = 2
