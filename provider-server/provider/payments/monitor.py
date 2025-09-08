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
                for vm_id, stream_id in items.items():
                    try:
                        s = self.reader.get_stream(stream_id)
                    except Exception as e:
                        logger.warning(f"stream {stream_id} lookup failed: {e}")
                        continue
                    # Stop VM if remaining runway < threshold
                    remaining = max(s["stopTime"] - now, 0)
                    if self.settings.STREAM_MONITOR_ENABLED and remaining < self.settings.STREAM_MIN_REMAINING_SECONDS:
                        logger.info(f"Stopping VM {vm_id} due to low stream runway ({remaining}s)")
                        try:
                            await self.vm_service.stop_vm(vm_id)
                        except Exception as e:
                            logger.warning(f"stop_vm failed for {vm_id}: {e}")
                    # Withdraw if enough vested and configured
                    if self.settings.STREAM_WITHDRAW_ENABLED and self.client:
                        vested = max(min(now, s["stopTime"]) - s["startTime"], 0) * s["ratePerSecond"]
                        withdrawable = max(vested - s["withdrawn"], 0)
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
