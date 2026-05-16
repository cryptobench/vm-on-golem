from typing import Any

from pydantic import BaseModel, Field


class VMRecord(BaseModel):
    name: str
    provider_ip: str
    vm_id: str
    config: dict[str, Any]
    status: str
    created_at: str | None = None


class CreateVMCommand(BaseModel):
    name: str = Field(..., min_length=1)
    provider_id: str = Field(..., min_length=1)
    cpu: int = Field(..., ge=1)
    memory: int = Field(..., ge=1)
    storage: int = Field(..., ge=1)
    ssh_key: str = Field(..., min_length=1)
    stream_id: int | None = None
    payment: dict[str, Any] | None = None


class ResizeVMCommand(BaseModel):
    cpu: int = Field(..., ge=1)
    memory: int = Field(..., ge=1)
    storage: int = Field(..., ge=1)
    stream_id: int | None = None


class CloneVMCommand(BaseModel):
    name: str = Field(..., min_length=1)
    stream_id: int | None = None


class SnapshotCommand(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    comment: str | None = None


class VMAccess(BaseModel):
    vm_id: str
    ssh_port: int | None = None
    ssh_host: str | None = None
    ssh_user: str | None = None


class VMCreateResult(BaseModel):
    name: str
    provider_ip: str
    vm_id: str
    config: dict[str, Any]
    status: str


class VMImage(BaseModel):
    alias: str
    version: str | None = None
    description: str | None = None


class VMSnapshot(BaseModel):
    name: str
    vm_id: str
    comment: str | None = None
    created_at: str | None = None
