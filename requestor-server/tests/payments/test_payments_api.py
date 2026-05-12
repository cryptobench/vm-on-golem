import pytest

from requestor.payments.api import terminate_stream
from requestor.payments.domain import StreamActionResult


class FakePaymentService:
    def __init__(self):
        self.terminated = []

    async def terminate_stream(self, stream_id: int) -> StreamActionResult:
        self.terminated.append(stream_id)
        return StreamActionResult(
            stream_id=stream_id,
            transaction_hash="0xtx",
            status="submitted",
        )


@pytest.mark.asyncio
async def test_terminate_stream_route_delegates_to_payment_service():
    payment_service = FakePaymentService()

    result = await terminate_stream(42, payment_service=payment_service)

    assert payment_service.terminated == [42]
    assert result.stream_id == 42
    assert result.transaction_hash == "0xtx"
