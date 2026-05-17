import inspect
import logging
from collections.abc import Callable
from typing import Any

from .domain import LeasePayment, StreamComputed, StreamOnChain, StreamStatus
from .errors import (
    InvalidStreamError,
    PaymentsDisabledError,
    StreamLookupError,
    StreamNotFoundError,
)
from .lease_quote_service import LeaseQuoteService

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

    async def require_valid_lease(
        self,
        payment: LeasePayment | None,
        *,
        requestor_address: str | None,
        current_vm_id: str | None = None,
        vm_name: str | None = None,
        image: str | None = None,
        resources: Any | None = None,
    ) -> None:
        if payment is None:
            raise InvalidStreamError("payment proof required when payments are enabled")
        if not requestor_address:
            raise InvalidStreamError("requestor action signature required")

        reader = self._reader()
        try:
            stream = reader.get_stream(payment.stream_id)
            now = int(reader.web3.eth.get_block("latest")["timestamp"])
        except Exception as exc:
            raise StreamLookupError(f"stream lookup failed: {exc}") from exc

        expected_recipient = str(self._setting("PROVIDER_ID", "") or "")
        expected_token = str(self._setting("GLM_TOKEN_ADDRESS", "") or "")
        expected_terms_hash = None
        if resources is not None:
            if payment.duration_seconds is None or int(payment.duration_seconds) <= 0:
                raise InvalidStreamError("payment duration required")
            chain_id = getattr(reader.web3.eth, "chain_id", None)
            if chain_id is None:
                chain_id = int(reader.web3.eth.get_block("latest").get("chainId", 0))
            if not chain_id:
                raise InvalidStreamError("chain id unavailable")
            stream_rate = int(stream["ratePerSecond"])
            expected_terms_hash = LeaseQuoteService._terms_hash(
                provider_address=expected_recipient,
                requestor_address=requestor_address,
                vm_name=vm_name or "",
                image=image or "",
                cpu=int(resources.cpu),
                memory=int(resources.memory),
                storage=int(resources.storage),
                rate_per_second=stream_rate,
                duration_seconds=int(payment.duration_seconds),
                contract_address=self._stream_contract_address(),
                glm_token_address=expected_token,
                chain_id=int(chain_id),
                lease_id=payment.lease_id,
            )
        checks = [
            (
                stream["recipient"].lower()
                != "0x0000000000000000000000000000000000000000",
                "stream terminated",
            ),
            (
                stream["recipient"].lower() == expected_recipient.lower(),
                "recipient mismatch",
            ),
            (stream["sender"].lower() == requestor_address.lower(), "sender mismatch"),
            (stream["token"].lower() == expected_token.lower(), "token mismatch"),
            (int(stream["stopTime"]) > now, "stream expired"),
            (
                int(stream["ratePerSecond"]) == int(payment.rate_per_second_wei),
                "stream rate mismatch",
            ),
            (
                _normalize_bytes32(stream["leaseId"])
                == _normalize_bytes32(payment.lease_id),
                "lease mismatch",
            ),
            (
                _normalize_bytes32(stream["termsHash"])
                == _normalize_bytes32(payment.terms_hash),
                "terms hash mismatch",
            ),
        ]
        if expected_terms_hash is not None:
            checks.append(
                (
                    _normalize_bytes32(payment.terms_hash)
                    == _normalize_bytes32(expected_terms_hash),
                    "quoted terms do not match VM request",
                )
            )
        for ok, reason in checks:
            if not ok:
                raise InvalidStreamError(f"invalid stream: {reason}")

        mapped = await self.stream_map.all_items()
        for vm_id, mapped_stream_id in mapped.items():
            if (
                int(mapped_stream_id) == int(payment.stream_id)
                and vm_id != current_vm_id
            ):
                raise InvalidStreamError("stream already mapped to another VM")

    async def require_vm_action_authorized(
        self, vm_id: str, requestor_address: str | None
    ) -> None:
        if not await self.is_payment_required():
            return
        if not requestor_address:
            raise InvalidStreamError("requestor action signature required")

        owner = None
        get_owner = getattr(self.stream_map, "get_owner", None)
        if get_owner is not None:
            owner = await get_owner(vm_id)
        if owner:
            if owner.lower() != requestor_address.lower():
                raise InvalidStreamError("requestor signer mismatch")
            return

        stream_id = await self.stream_map.get(vm_id)
        if stream_id is None:
            raise InvalidStreamError("no payment stream mapped for VM")
        reader = self._reader()
        try:
            stream = reader.get_stream(int(stream_id))
        except Exception as exc:
            raise StreamLookupError(f"stream lookup failed: {exc}") from exc
        sender = str(stream.get("sender") or "")
        if sender.lower() != requestor_address.lower():
            raise InvalidStreamError("requestor signer mismatch")

    async def is_payment_required(self) -> bool:
        address = str(self._setting("STREAM_PAYMENT_ADDRESS", "") or "")
        return bool(address and address != ZERO_ADDRESS)

    async def set_vm_stream(
        self,
        vm_id: str,
        stream_id: int | None,
        requestor_address: str | None = None,
    ) -> None:
        if stream_id is not None:
            if len(inspect.signature(self.stream_map.set).parameters) >= 3:
                await self.stream_map.set(vm_id, int(stream_id), requestor_address)
            else:
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
        record = await self._stream_record(vm_id)
        if record is None:
            raise StreamNotFoundError("no stream mapped for this VM")
        return self._build_status(reader, vm_id, int(record["stream_id"]))

    async def list_stream_statuses(self) -> list[StreamStatus]:
        reader = self._reader()
        items = await self.stream_map.active_items()
        return [
            self._build_status(reader, vm_id, int(stream_id))
            for vm_id, stream_id in items.items()
        ]

    async def verify_vm_stream_terminated(self, vm_id: str) -> dict[str, Any]:
        reader = self._reader()
        record = await self._stream_record(vm_id)
        if record is None:
            raise StreamNotFoundError("no stream mapped for this VM")
        try:
            stream = reader.get_stream(int(record["stream_id"]))
        except Exception as exc:
            raise StreamLookupError(f"stream lookup failed: {exc}") from exc
        if not _stream_is_terminated(stream):
            raise InvalidStreamError("stream is still active")
        return stream

    async def terminal_record(self, vm_id: str) -> dict[str, Any] | None:
        record = await self._stream_record(vm_id)
        if record and record.get("state") == "terminated":
            return record
        return None

    async def mark_vm_stream_terminated(
        self,
        vm_id: str,
        *,
        terminated_by: str,
        termination_reason: str,
        settlement_tx_hash: str | None,
        cleanup_state: str,
    ) -> dict[str, Any]:
        mark_terminated = getattr(self.stream_map, "mark_terminated")
        return await mark_terminated(
            vm_id,
            terminated_by=terminated_by,
            termination_reason=termination_reason,
            settlement_tx_hash=settlement_tx_hash,
            cleanup_state=cleanup_state,
        )

    async def set_vm_stream_cleanup_state(
        self, vm_id: str, cleanup_state: str
    ) -> dict[str, Any]:
        set_cleanup_state = getattr(self.stream_map, "set_cleanup_state")
        return await set_cleanup_state(vm_id, cleanup_state)

    async def active_stream_items(self) -> dict[str, int]:
        return await self.stream_map.active_items()

    async def _stream_record(self, vm_id: str) -> dict[str, Any] | None:
        get_record = getattr(self.stream_map, "get_record", None)
        if get_record is None:
            raise RuntimeError("structured stream map is required")
        return await get_record(vm_id)

    def _build_status(self, reader: Any, vm_id: str, stream_id: int) -> StreamStatus:
        try:
            stream = reader.get_stream(stream_id)
            now = int(reader.web3.eth.get_block("latest")["timestamp"])
            ok, reason = reader.verify_stream(
                stream_id, str(self._setting("PROVIDER_ID", "") or "")
            )
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
            payment_state=_payment_state(stream, now, ok),
        )


def _normalize_bytes32(value: str) -> str:
    raw = str(value)
    return raw.lower() if raw.startswith("0x") else f"0x{raw.lower()}"


def _payment_state(stream: dict, now: int, verified: bool) -> str:
    if _stream_is_terminated(stream):
        return "terminated"
    if int(stream["stopTime"]) <= now:
        return "expired"
    if verified:
        return "active"
    return "invalid"


def _stream_is_terminated(stream: dict) -> bool:
    return str(stream["recipient"]).lower() == ZERO_ADDRESS
