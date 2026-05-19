import asyncio
from typing import Optional

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class StreamMonitor:
    def __init__(
        self,
        *,
        stream_map,
        vm_application_service,
        reader,
        client,
        settings,
        webhook_service=None,
    ):
        self.stream_map = stream_map
        self.vm_application_service = vm_application_service
        self.reader = reader
        self.client = client
        self.settings = settings
        self.webhook_service = webhook_service
        self._task: Optional[asyncio.Task] = None

    def _get(self, key: str, default=None):
        """Safely read setting from either an object with attributes or a dict-like mapping."""
        try:
            return getattr(self.settings, key)
        except Exception:
            try:
                return self.settings.get(key, default)
            except Exception:
                return default

    def start(self):
        if self._get("STREAM_MONITOR_ENABLED", False) or self._get(
            "STREAM_WITHDRAW_ENABLED", False
        ):
            logger.info(
                f"⏱️ Stream monitor enabled (check={self._get('STREAM_MONITOR_ENABLED', False)}, "
                f"withdraw={self._get('STREAM_WITHDRAW_ENABLED', False)}) interval={self._get('STREAM_MONITOR_INTERVAL_SECONDS', 60)}s"
            )
            self._task = asyncio.create_task(self._run(), name="stream-monitor")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        last_withdraw = 0
        while True:
            try:
                await asyncio.sleep(
                    int(self._get("STREAM_MONITOR_INTERVAL_SECONDS", 60))
                )
                items = await self.stream_map.active_items()
                now = (
                    int(self.reader.web3.eth.get_block("latest")["timestamp"])
                    if items
                    else 0
                )
                logger.debug(f"stream monitor tick: {len(items)} streams, now={now}")
                for vm_id, stream_id in items.items():
                    try:
                        s = self.reader.get_stream(stream_id)
                    except Exception as e:
                        logger.error(
                            "Stream lookup failed during monitor tick",
                            extra={"vm_id": vm_id, "stream_id": int(stream_id)},
                            exc_info=True,
                        )
                        await self._emit_stream_lost(
                            vm_id,
                            stream_id,
                            "stream lookup failed",
                            {"error": str(e)},
                        )
                        continue
                    # Stop VM if remaining runway < threshold
                    remaining = max(int(s["stopTime"]) - int(now), 0)
                    logger.debug(
                        f"stream {stream_id} for VM {vm_id}: start={s['startTime']} stop={s['stopTime']} "
                        f"rate={s['ratePerSecond']} withdrawn={s['withdrawn']} remaining={remaining}s"
                    )
                    # If stream is terminated, delete immediately to free all resources.
                    if (
                        str(s.get("recipient", "")).lower()
                        == "0x0000000000000000000000000000000000000000"
                    ):
                        logger.info(
                            f"Deleting VM {vm_id} due to terminated stream (id={stream_id}, now={now})"
                        )
                        await self._emit_stream_lost(
                            vm_id,
                            stream_id,
                            "stream terminated",
                            {"remaining_seconds": remaining},
                        )
                        try:
                            await self.vm_application_service.cleanup_requestor_terminated_stream(
                                vm_id, stream_id
                            )
                        except Exception as e:
                            logger.error(
                                "VM cleanup failed after stream termination",
                                extra={"vm_id": vm_id, "stream_id": int(stream_id)},
                                exc_info=True,
                            )
                            continue
                        continue

                    if remaining == 0:
                        await self._emit_stream_lost(
                            vm_id,
                            stream_id,
                            "stream exhausted",
                            {"remaining_seconds": remaining},
                        )
                        try:
                            cleaned = await self.vm_application_service.expire_vm_lease(
                                vm_id, stream_id
                            )
                        except Exception:
                            logger.error(
                                "Expired stream VM cleanup failed",
                                extra={"vm_id": vm_id, "stream_id": int(stream_id)},
                                exc_info=True,
                            )
                            continue
                        if cleaned:
                            logger.info(
                                "Expired stream VM cleanup completed",
                                extra={"vm_id": vm_id, "stream_id": int(stream_id)},
                            )
                            continue
                        logger.info(
                            "Payment stream has no remaining runway but is still in grace",
                            extra={"vm_id": vm_id, "stream_id": int(stream_id)},
                        )
                        continue

                    # Otherwise, do not stop; just log health and consider withdrawals
                    logger.debug(
                        f"VM {vm_id} stream {stream_id} healthy (remaining={remaining}s)"
                    )
                    # Withdraw if enough vested and configured
                    if self._get("STREAM_WITHDRAW_ENABLED", False) and self.client:
                        vested = (
                            max(min(now, s["stopTime"]) - s["startTime"], 0)
                            * s["ratePerSecond"]
                        )
                        withdrawable = max(vested - s["withdrawn"], 0)
                        logger.debug(
                            f"withdraw check stream {stream_id}: vested={vested} withdrawable={withdrawable}"
                        )
                        # Enforce a minimum interval between withdrawals
                        if withdrawable >= int(
                            self._get("STREAM_MIN_WITHDRAW_WEI", 0)
                        ) and (
                            now - last_withdraw
                            >= int(self._get("STREAM_WITHDRAW_INTERVAL_SECONDS", 1800))
                        ):
                            try:
                                tx_hash = self.client.withdraw(stream_id)
                                last_withdraw = now
                                logger.info(
                                    "Provider stream withdrawal submitted",
                                    extra={
                                        "stream_id": stream_id,
                                        "vm_id": vm_id,
                                        "transaction_hash": tx_hash,
                                    },
                                )
                            except Exception as e:
                                logger.warning(f"withdraw failed for {stream_id}: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"stream monitor error: {e}", exc_info=True)

    async def _emit_stream_lost(
        self, vm_id: str, stream_id: int, reason: str, data: dict
    ) -> None:
        if self.webhook_service is None:
            return
        await self.webhook_service.emit(
            "payment.stream.lost",
            resource_type="stream",
            resource_id=str(stream_id),
            severity="critical",
            summary="Payment stream lost",
            data={"vm_id": vm_id, "reason": reason, **data},
        )
