import asyncio
import json
import logging
from typing import Any

import websockets
from web3 import Web3

from provider.live.events import ProviderEventBroadcaster

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
logger = logging.getLogger(__name__)

STREAM_PAYMENT_EVENT_TOPICS = {
    Web3.keccak(
        text="StreamCreated(uint256,address,address,address,uint256,uint256,uint256,uint256,bytes32,bytes32)"
    )
    .hex()
    .lower(): "StreamCreated",
    Web3.keccak(text="Withdraw(uint256,address,uint256)").hex().lower(): "Withdraw",
    Web3.keccak(text="Terminated(uint256,uint256,uint256)").hex().lower(): "Terminated",
    Web3.keccak(text="ToppedUp(uint256,uint256,uint128)").hex().lower(): "ToppedUp",
}


class StreamPaymentEventService:
    """Subscribes to StreamPayment contract events and invalidates live read models."""

    def __init__(
        self,
        *,
        settings: Any,
        stream_map: Any,
        reader_factory: Any,
        broadcaster: ProviderEventBroadcaster,
    ):
        self.settings = settings
        self.stream_map = stream_map
        self.reader_factory = reader_factory
        self.broadcaster = broadcaster
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def start(self) -> None:
        if not self._payments_enabled():
            return
        ws_url = str(self._setting("PAYMENTS_WS_URL", "") or "").strip()
        if not ws_url:
            raise RuntimeError("PAYMENTS_WS_URL is required when payments are enabled")
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run(ws_url), name="stream-payment-events"
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def _payments_enabled(self) -> bool:
        address = str(self._setting("STREAM_PAYMENT_ADDRESS", "") or "").lower()
        return bool(address and address != ZERO_ADDRESS)

    async def _run(self, ws_url: str) -> None:
        retry_seconds = 1
        while not self._stop_event.is_set():
            try:
                await self._subscribe(ws_url)
                retry_seconds = 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "StreamPayment websocket event subscription failed",
                    extra={"retry_seconds": retry_seconds},
                    exc_info=True,
                )
                await asyncio.sleep(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 30)

    async def _subscribe(self, ws_url: str) -> None:
        address = Web3.to_checksum_address(str(self._setting("STREAM_PAYMENT_ADDRESS")))
        async with websockets.connect(ws_url) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "eth_subscribe",
                        "params": ["logs", {"address": address}],
                    }
                )
            )
            response = json.loads(await websocket.recv())
            if "error" in response:
                raise RuntimeError(f"eth_subscribe failed: {response['error']}")
            subscription_id = response.get("result")
            if not subscription_id:
                raise RuntimeError("eth_subscribe did not return a subscription id")
            logger.info(
                "StreamPayment websocket event subscription opened",
                extra={"subscription_id": subscription_id},
            )
            while not self._stop_event.is_set():
                message = json.loads(await websocket.recv())
                if message.get("method") != "eth_subscription":
                    continue
                result = (message.get("params") or {}).get("result")
                if isinstance(result, dict):
                    await self._handle_log(result)

    async def _handle_log(self, log: dict[str, Any]) -> None:
        topics = log.get("topics") or []
        if len(topics) < 2:
            logger.warning("StreamPayment event log missing indexed stream id")
            return
        event_name = STREAM_PAYMENT_EVENT_TOPICS.get(str(topics[0]).lower())
        if event_name is None:
            return
        stream_id = int(str(topics[1]), 16)
        try:
            self.reader_factory().get_stream(stream_id)
        except Exception:
            logger.error(
                "StreamPayment event stream refetch failed",
                extra={"stream_id": stream_id, "event_name": event_name},
                exc_info=True,
            )
            raise

        await self.broadcaster.publish_provider(["streams", "summary"])
        vm_ids = await self._vm_ids_for_stream(stream_id)
        for vm_id in vm_ids:
            await self.broadcaster.publish_vm(vm_id, ["stream"])
        logger.info(
            "StreamPayment event invalidated live stream state",
            extra={
                "stream_id": stream_id,
                "event_name": event_name,
                "vm_ids": ",".join(vm_ids),
            },
        )

    async def _vm_ids_for_stream(self, stream_id: int) -> list[str]:
        items = await self.stream_map.all_items()
        return [
            vm_id for vm_id, mapped_id in items.items() if int(mapped_id) == stream_id
        ]
