import logging
from collections.abc import Callable
from typing import Any

from .domain import StreamComputed, StreamOnChain, StreamStatus
from .errors import (
    InvalidStreamError,
    PaymentsDisabledError,
    StreamLookupError,
    StreamNotFoundError,
)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
logger = logging.getLogger(__name__)


class StreamStatusService:
    """Business logic for stream payment validation and status projection."""

    def __init__(
        self, settings: Any, stream_map: Any, reader_factory: Callable[[], Any]
    ):
        self.settings = settings
        self.stream_map = stream_map
        self.reader_factory = reader_factory

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def _stream_contract_address(self) -> str:
        address = str(self._setting("STREAM_PAYMENT_ADDRESS", "") or "")
        if not address or address == ZERO_ADDRESS:
            raise PaymentsDisabledError(
                "streaming payments not enabled on this provider"
            )
        return address

    def _reader(self) -> Any:
        self._stream_contract_address()
        return self.reader_factory()

    async def require_valid_stream(self, stream_id: int | None) -> None:
        if stream_id is None:
            logger.warning("Payment stream validation failed: stream_id missing")
            raise InvalidStreamError("stream_id required when payments are enabled")

        logger.info("Validating payment stream", extra={"stream_id": stream_id})
        reader = self._reader()
        expected_recipient = str(self._setting("PROVIDER_ID", "") or "")
        ok, reason = reader.verify_stream(int(stream_id), expected_recipient)
        if not ok:
            logger.warning(
                "Payment stream validation failed",
                extra={"stream_id": stream_id, "reason": reason},
            )
            raise InvalidStreamError(f"invalid stream: {reason}")
        logger.info("Payment stream validated", extra={"stream_id": stream_id})

    async def is_payment_required(self) -> bool:
        address = str(self._setting("STREAM_PAYMENT_ADDRESS", "") or "")
        return bool(address and address != ZERO_ADDRESS)

    async def set_vm_stream(self, vm_id: str, stream_id: int | None) -> None:
        if stream_id is not None:
            await self.stream_map.set(vm_id, int(stream_id))
            logger.info(
                "VM stream mapping set",
                extra={"vm_id": vm_id, "stream_id": int(stream_id)},
            )

    async def remove_vm_stream(self, vm_id: str) -> None:
        await self.stream_map.remove(vm_id)
        logger.info("VM stream mapping removed", extra={"vm_id": vm_id})

    async def get_vm_stream_status(self, vm_id: str) -> StreamStatus:
        reader = self._reader()
        stream_id = await self.stream_map.get(vm_id)
        if stream_id is None:
            raise StreamNotFoundError("no stream mapped for this VM")
        return self._build_status(reader, vm_id, int(stream_id))

    async def list_stream_statuses(self) -> list[StreamStatus]:
        reader = self._reader()
        items = await self.stream_map.all_items()
        return [
            self._build_status(reader, vm_id, int(stream_id))
            for vm_id, stream_id in items.items()
        ]

    def _build_status(self, reader: Any, vm_id: str, stream_id: int) -> StreamStatus:
        try:
            stream = reader.get_stream(stream_id)
            ok, reason = reader.verify_stream(
                stream_id, str(self._setting("PROVIDER_ID", "") or "")
            )
            now = int(reader.web3.eth.get_block("latest")["timestamp"])
        except Exception as exc:
            logger.error(
                "Payment stream lookup failed",
                extra={"vm_id": vm_id, "stream_id": stream_id},
                exc_info=True,
            )
            raise StreamLookupError(f"stream lookup failed: {exc}") from exc

        vested = max(
            min(now, int(stream["stopTime"])) - int(stream["startTime"]), 0
        ) * int(stream["ratePerSecond"])
        withdrawable = max(int(vested) - int(stream["withdrawn"]), 0)
        remaining = max(int(stream["stopTime"]) - now, 0)

        return StreamStatus(
            vm_id=vm_id,
            stream_id=stream_id,
            chain=StreamOnChain(**stream),
            computed=StreamComputed(
                now=now,
                remaining_seconds=remaining,
                vested_wei=int(vested),
                withdrawable_wei=int(withdrawable),
            ),
            verified=bool(ok),
            reason=str(reason),
        )
