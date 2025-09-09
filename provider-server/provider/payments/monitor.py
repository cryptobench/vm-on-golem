import asyncio
from typing import Optional

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class StreamMonitor:
    def __init__(self, *, stream_map, vm_service, reader, client, settings):
        self.stream_map = stream_map
        self.vm_service = vm_service
        self.reader = reader
        self.client = client
        self.settings = settings
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if self.settings.STREAM_MONITOR_ENABLED or self.settings.STREAM_WITHDRAW_ENABLED:
            logger.info(
                f"⏱️ Stream monitor enabled (check={self.settings.STREAM_MONITOR_ENABLED}, withdraw={self.settings.STREAM_WITHDRAW_ENABLED}) "
                f"interval={self.settings.STREAM_MONITOR_INTERVAL_SECONDS}s"
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
                await asyncio.sleep(self.settings.STREAM_MONITOR_INTERVAL_SECONDS)
                items = await self.stream_map.all_items()
                now = int(self.reader.web3.eth.get_block("latest")["timestamp"]) if items else 0
                logger.debug(f"stream monitor tick: {len(items)} streams, now={now}")
                for vm_id, stream_id in items.items():
                    try:
                        s = self.reader.get_stream(stream_id)
                    except Exception as e:
                        logger.warning(f"stream {stream_id} lookup failed: {e}")
                        continue
                    # Stop VM if remaining runway < threshold
                    remaining = max(s["stopTime"] - now, 0)
                    logger.debug(
                        f"stream {stream_id} for VM {vm_id}: start={s['startTime']} stop={s['stopTime']} "
                        f"rate={s['ratePerSecond']} withdrawn={s['withdrawn']} halted={s['halted']} remaining={remaining}s"
                    )
                    if self.settings.STREAM_MONITOR_ENABLED and remaining < self.settings.STREAM_MIN_REMAINING_SECONDS:
                        logger.info(f"Stopping VM {vm_id} due to low stream runway ({remaining}s)")
                        try:
                            await self.vm_service.stop_vm(vm_id)
                        except Exception as e:
                            logger.warning(f"stop_vm failed for {vm_id}: {e}")
                    else:
                        logger.debug(
                            f"VM {vm_id} stream {stream_id} healthy (remaining={remaining}s, threshold={self.settings.STREAM_MIN_REMAINING_SECONDS}s)"
                        )
                    # Withdraw if enough vested and configured
                    if self.settings.STREAM_WITHDRAW_ENABLED and self.client:
                        vested = max(min(now, s["stopTime"]) - s["startTime"], 0) * s["ratePerSecond"]
                        withdrawable = max(vested - s["withdrawn"], 0)
                        logger.debug(f"withdraw check stream {stream_id}: vested={vested} withdrawable={withdrawable}")
                        # Enforce a minimum interval between withdrawals
                        if withdrawable >= self.settings.STREAM_MIN_WITHDRAW_WEI and (
                            now - last_withdraw >= self.settings.STREAM_WITHDRAW_INTERVAL_SECONDS
                        ):
                            try:
                                self.client.withdraw(stream_id)
                                last_withdraw = now
                            except Exception as e:
                                logger.warning(f"withdraw failed for {stream_id}: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"stream monitor error: {e}")
