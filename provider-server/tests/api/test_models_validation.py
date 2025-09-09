import pytest
from pydantic import ValidationError

from provider.api.models import CreateVMRequest
from provider.vm.models import VMResources, VMSize


def test_create_vm_request_name_rejects_double_hyphen():
    with pytest.raises(ValidationError):
        CreateVMRequest(
            name="bad--name",
            ssh_key="ssh-rsa AAA...",
            resources={"cpu": 1, "memory": 1, "storage": 10},
        )


def test_create_vm_request_accepts_vmresources_instance():
    req = CreateVMRequest(
        name="okname",
        ssh_key="ssh-rsa AAA...",
        resources=VMResources(cpu=1, memory=1, storage=10),
    )
    assert req.resources.cpu == 1
    assert req.resources.memory == 1
    assert req.resources.storage == 10


def test_create_vm_request_uses_size_when_no_resources():
    # Call the validator directly to exercise the size path
    from types import SimpleNamespace
    v = None
    values = SimpleNamespace(data={"size": VMSize.MEDIUM})
    out = CreateVMRequest.validate_resources(v, values)  # type: ignore[arg-type]
    assert isinstance(out, VMResources)
    assert out.cpu == 2 and out.memory == 4 and out.storage == 20


def test_create_vm_request_defaults_when_no_size_or_resources():
    # Call the validator directly to exercise defaults path
    from types import SimpleNamespace
    v = None
    values = SimpleNamespace(data={})
    out = CreateVMRequest.validate_resources(v, values)  # type: ignore[arg-type]
    assert isinstance(out, VMResources)
    assert out.cpu == 1 and out.memory == 1 and out.storage == 10
