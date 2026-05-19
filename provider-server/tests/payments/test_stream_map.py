import json

import pytest

from provider.payments.stream_map import StreamMap


@pytest.mark.asyncio
async def test_stream_map_uses_structured_active_and_terminal_records(tmp_path):
    stream_map = StreamMap(tmp_path / "streams.json")

    await stream_map.set("vm-a", 42, "0xrequestor")

    assert await stream_map.get("vm-a") == 42
    assert await stream_map.get_owner("vm-a") == "0xrequestor"
    assert await stream_map.active_items() == {"vm-a": 42}

    record = await stream_map.mark_terminated(
        "vm-a",
        terminated_by="requestor",
        termination_reason="requestor_terminated",
        settlement_tx_hash="0xtx",
        cleanup_state="completed",
    )

    assert record["state"] == "terminated"
    assert await stream_map.get("vm-a") is None
    assert await stream_map.get_owner("vm-a") == "0xrequestor"
    assert await stream_map.active_items() == {}

    await stream_map.set("vm-b", 43, "0xrequestor")
    expired_record = await stream_map.mark_terminated(
        "vm-b",
        terminated_by="provider",
        termination_reason="stream_expired",
        settlement_tx_hash=None,
        cleanup_state="completed",
    )

    assert expired_record["termination_reason"] == "stream_expired"


def test_stream_map_rejects_legacy_unstructured_entries(tmp_path):
    path = tmp_path / "streams.json"
    path.write_text(json.dumps({"vm-a": 42}))

    with pytest.raises(ValueError, match="legacy entry"):
        StreamMap(path)
