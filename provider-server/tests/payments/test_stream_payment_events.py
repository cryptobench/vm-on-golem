import pytest

from provider.live.events import LiveInvalidationBus
from provider.payments.events import (
    STREAM_PAYMENT_EVENT_TOPICS,
    StreamPaymentEventService,
)


class StubStreamMap:
    async def all_items(self):
        return {"vm-1": 7, "vm-2": 99}


class StubReader:
    def __init__(self):
        self.stream_ids = []

    def get_stream(self, stream_id):
        self.stream_ids.append(stream_id)
        return {"id": stream_id}


def _topic_for(event_name: str) -> str:
    for topic, name in STREAM_PAYMENT_EVENT_TOPICS.items():
        if name == event_name:
            return topic
    raise AssertionError(f"missing topic for {event_name}")


def _stream_id_topic(stream_id: int) -> str:
    return f"0x{stream_id:064x}"


def test_start_requires_ws_url_when_payments_enabled():
    service = StreamPaymentEventService(
        settings={
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "PAYMENTS_WS_URL": "",
        },
        stream_map=StubStreamMap(),
        reader_factory=StubReader,
        broadcaster=LiveInvalidationBus(),
    )

    with pytest.raises(RuntimeError, match="PAYMENTS_WS_URL is required"):
        service.start()


@pytest.mark.asyncio
async def test_stream_event_refetches_stream_and_invalidates_live_scopes():
    reader = StubReader()
    broadcaster = LiveInvalidationBus()
    service = StreamPaymentEventService(
        settings={
            "STREAM_PAYMENT_ADDRESS": "0x1111111111111111111111111111111111111111",
            "PAYMENTS_WS_URL": "wss://payments.example",
        },
        stream_map=StubStreamMap(),
        reader_factory=lambda: reader,
        broadcaster=broadcaster,
    )

    async with broadcaster.subscribe_provider() as provider_queue:
        async with broadcaster.subscribe_vm("vm-1") as vm_queue:
            await service._handle_log(
                {
                    "topics": [
                        _topic_for("Withdraw"),
                        _stream_id_topic(7),
                    ]
                }
            )

            assert reader.stream_ids == [7]
            assert await provider_queue.get() == {"streams", "summary"}
            assert await vm_queue.get() == {"stream"}
