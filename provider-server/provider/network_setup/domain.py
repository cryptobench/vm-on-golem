from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SetupStageName(str, Enum):
    PUBLIC_IP = "public_ip"
    NETWORK_ACCESS = "network_access"
    CERTIFICATE = "certificate"
    HTTPS_VERIFICATION = "https_verification"
    VM_PORT_RANGE = "vm_port_range"
    PROVIDER_START = "provider_start"


class SetupStageState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PortCheck(BaseModel):
    port: int
    state: Literal["pending", "checking", "open", "closed"] = "pending"


class SetupStage(BaseModel):
    name: SetupStageName
    state: SetupStageState = SetupStageState.PENDING
    label: str
    detail: str = ""
    remediation: str | None = None
    port_checks: list[PortCheck] = Field(default_factory=list)


class StartupSetupStatus(BaseModel):
    stages: list[SetupStage] = Field(default_factory=list)
    endpoint_url: str | None = None
    api_http_public_port: int | None = None
    api_https_public_port: int | None = None
    vm_port_range_start: int | None = None
    vm_port_range_end: int | None = None
    message: str = ""

    @property
    def failed(self) -> bool:
        return any(stage.state == SetupStageState.FAILED for stage in self.stages)

    @property
    def complete(self) -> bool:
        return all(stage.state == SetupStageState.SUCCESS for stage in self.stages)

    def stage(self, name: SetupStageName) -> SetupStage:
        for stage in self.stages:
            if stage.name == name:
                return stage
        raise KeyError(name)


class NetworkSetupError(RuntimeError):
    def __init__(self, message: str, status: StartupSetupStatus | None = None):
        super().__init__(message)
        self.status = status
