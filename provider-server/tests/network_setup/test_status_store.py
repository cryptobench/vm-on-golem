from types import SimpleNamespace

import pytest

from provider.network_setup.domain import (
    PortCheck,
    SetupStage,
    SetupStageName,
    SetupStageState,
    StartupSetupStatus,
)
from provider.network_setup.status_store import (
    read_startup_setup_status,
    startup_setup_status_path,
    write_startup_setup_status,
)


def _settings(tmp_path, start=50800, end=50802):
    return SimpleNamespace(
        PROXY_STATE_DIR=str(tmp_path),
        PORT_RANGE_START=start,
        PORT_RANGE_END=end,
    )


def _status(start=50800, end=50802):
    return StartupSetupStatus(
        endpoint_url="https://203.0.113.10",
        vm_port_range_start=start,
        vm_port_range_end=end,
        stages=[
            SetupStage(
                name=SetupStageName.VM_PORT_RANGE,
                label="VM ports reachable",
                state=SetupStageState.SUCCESS,
                detail=f"{start}-{end} reachable",
                port_checks=[
                    PortCheck(port=start, state="open"),
                    PortCheck(port=start + 1, state="open"),
                ],
            )
        ],
    )


def test_status_store_writes_and_reads_startup_status(tmp_path):
    settings = _settings(tmp_path)
    status = _status()

    write_startup_setup_status(settings, status)

    loaded = read_startup_setup_status(settings)
    assert loaded is not None
    assert loaded.endpoint_url == "https://203.0.113.10"
    assert loaded.stage(SetupStageName.VM_PORT_RANGE).port_checks[0].state == "open"


def test_status_store_missing_file_returns_none(tmp_path):
    assert read_startup_setup_status(_settings(tmp_path)) is None


def test_status_store_malformed_json_fails_visibly(tmp_path):
    settings = _settings(tmp_path)
    startup_setup_status_path(settings).write_text("{not json")

    with pytest.raises(RuntimeError, match="Failed to read startup setup status"):
        read_startup_setup_status(settings)


def test_status_store_current_range_mismatch_returns_none(tmp_path):
    write_startup_setup_status(_settings(tmp_path), _status(start=50800, end=50802))

    assert (
        read_startup_setup_status(_settings(tmp_path, start=50900, end=51000)) is None
    )
