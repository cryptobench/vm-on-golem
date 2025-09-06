# Test Coverage Report

This document outlines the test coverage for the provider server, detailing both happy and unhappy path tests for each module.

## API Routes (`tests/api/test_routes.py`)

### Happy Paths

- `test_create_vm_happy_path`: Tests successful VM creation.
- `test_list_vms_happy_path`: Tests successful listing of VMs.
- `test_get_vm_status_happy_path`: Tests successful retrieval of a VM's status.
- `test_delete_vm_happy_path`: Tests successful deletion of a VM.

### Unhappy Paths

- `test_create_vm_invalid_data`: Tests VM creation with invalid data (missing `ssh_key`).
- `test_get_vm_status_not_found`: Tests retrieving the status of a non-existent VM.
- `test_delete_vm_not_found`: Tests deleting a non-existent VM.
- `test_create_vm_service_exception`: Tests handling of a service exception during VM creation.
- `test_get_vm_status_service_exception`: Tests handling of a service exception when retrieving VM status.
- `test_delete_vm_service_exception`: Tests handling of a service exception during VM deletion.

## Multipass Adapter (`tests/vm/test_multipass_adapter.py`)

### Happy Paths

- `test_verify_installation_success`: Tests that the Multipass installation is correctly verified.
- `test_create_vm_happy_path`: Tests successful VM creation using Multipass.
- `test_delete_vm_happy_path`: Tests successful VM deletion using Multipass.
- `test_get_vm_status_happy_path`: Tests successful retrieval of a VM's status from Multipass.

### Unhappy Paths

- `test_verify_installation_failure`: Tests the handling of a failed Multipass installation verification.
- `test_create_vm_multipass_fails`: Tests the handling of a Multipass command failure during VM creation.
- `test_delete_vm_does_not_exist`: Tests that no error is raised when attempting to delete a VM that does not exist.
- `test_get_vm_status_vm_not_found`: Tests for a `VMNotFoundError` when the VM is not found in Multipass.
- `test_create_vm_get_status_fails`: Tests the scenario where getting the VM status fails after creation.
- `test_delete_vm_multipass_fails`: Tests the handling of a Multipass command failure during VM deletion.
- `test_get_vm_status_not_running`: Tests getting the status of a VM that is not in a "RUNNING" state.
- `test_get_vm_status_no_ipv4`: Tests getting the status of a running VM that does not have an IPv4 address.

## VM Service (`tests/vm/test_vm_service.py`)

### Happy Paths

- `test_create_vm_happy_path`: Tests the successful creation of a VM, including resource allocation and provider interaction.
- `test_delete_vm_happy_path`: Tests the successful deletion of a VM, including deallocation of resources.
- `test_list_vms_no_vms`: Tests listing VMs when there are none.
- `test_list_vms_with_vms`: Tests listing VMs when there are existing VMs.
- `test_get_vm_status_happy_path`: Tests successful retrieval of a VM's status.

### Unhappy Paths

- `test_create_vm_allocation_fails`: Tests the scenario where resource allocation fails during VM creation.
- `test_create_vm_provider_fails_deallocates`: Tests that resources are deallocated if the VM provider fails during creation.
- `test_delete_vm_does_not_exist`: Tests for a `VMNotFoundError` when trying to delete a non-existent VM.
- `test_delete_vm_provider_fails`: Tests the handling of a provider failure during VM deletion.
- `test_get_vm_status_does_not_exist`: Tests for a `VMNotFoundError` when getting the status of a non-existent VM.


## Missing Tests

Based on the current test suite, here are some potential areas for improvement:

### API Routes (`tests/api/test_routes.py`)

- **`list_vms` Unhappy Path**: No test exists for when the `vm_service` raises an exception during the listing of VMs.
- **Invalid VM Configuration**: Tests for creating a VM with invalid resource requests (e.g., negative CPU, memory, or storage) are missing.
- **Invalid SSH Key Format**: No test covers the case where an `ssh_key` with an invalid format is provided.

### Multipass Adapter (`tests/vm/test_multipass_adapter.py`)

- **`_run_multipass` Helper**: The `_run_multipass` helper function is not directly tested for cases where `subprocess.run` might raise exceptions.
- **`_parse_vm_info` Edge Cases**: While tested indirectly, direct tests for `_parse_vm_info` with different JSON outputs from Multipass (e.g., missing fields, unexpected formats) would be beneficial.
- **Resource Edge Cases**: Tests for creating a VM with very large or zero values for CPU, memory, and storage are not present.

### VM Service (`tests/vm/test_vm_service.py`)

- **`initialize` and `shutdown` Methods**: The `initialize` and `shutdown` methods of the `VMService` are not currently covered by tests.
- **Concurrency**: While more of an integration test, scenarios involving concurrent requests to create or delete VMs are not tested.
