from __future__ import annotations

from typing import Awaitable, Callable

from pydantic import BaseModel, Field

from .models import VMStatus, is_transitioning
from .models import status_message as message_for_status
from .models import status_progress


class VMLifecycleState(BaseModel):
    """Provider-facing lifecycle projection for VM transitions."""

    status: VMStatus
    lifecycle_stage: str
    status_message: str
    progress: int = Field(..., ge=0, le=100)
    transitioning: bool
    next_poll_seconds: int = Field(default=2, ge=1)


ProgressCallback = Callable[[VMLifecycleState], Awaitable[None]]


def lifecycle_for_status(
    status: VMStatus | str | None,
    *,
    stage: str | None = None,
    message: str | None = None,
    progress: int | None = None,
) -> VMLifecycleState:
    vm_status = (
        status if isinstance(status, VMStatus) else VMStatus.from_multipass(status)
    )
    transitioning = is_transitioning(vm_status)
    resolved_stage = stage or vm_status.value
    resolved_progress = progress
    if resolved_progress is None:
        resolved_progress = status_progress(vm_status)

    return VMLifecycleState(
        status=vm_status,
        lifecycle_stage=resolved_stage,
        status_message=message or message_for_status(vm_status),
        progress=max(0, min(100, int(resolved_progress))),
        transitioning=transitioning,
        next_poll_seconds=2 if transitioning else 8,
    )


def creation_lifecycle(
    stage: str,
    message: str,
    progress: int,
) -> VMLifecycleState:
    return lifecycle_for_status(
        VMStatus.CREATING,
        stage=stage,
        message=message,
        progress=progress,
    )
