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
