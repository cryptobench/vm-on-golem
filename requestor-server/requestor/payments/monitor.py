import asyncio
from typing import Optional

from ..services.database_service import DatabaseService
from ..provider.client import ProviderClient
from ..config import config
from ..utils.logging import setup_logger
from .blockchain_service import StreamPaymentClient, StreamPaymentConfig


class RequestorStreamMonitor:
    def __init__(self, db: DatabaseService):
        self.db = db
        self._task: Optional[asyncio.Task] = None
        self._logger = setup_logger(__name__)
        self._sp = StreamPaymentClient(
            StreamPaymentConfig(
                rpc_url=config.polygon_rpc_url,
                contract_address=config.stream_payment_address,
                glm_token_address=config.glm_token_address,
                private_key=config.ethereum_private_key,
            )
        )

    def start(self):
        if not config.stream_monitor_enabled:
            return
        self._logger.info(
            f"⏱️ Requestor stream auto-topup enabled interval={config.stream_monitor_interval_seconds}s "
            f"min_remaining={config.stream_min_remaining_seconds}s target={config.stream_topup_target_seconds}s"
        )
        self._task = asyncio.create_task(self._run(), name="requestor-stream-monitor")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._logger.info("Requestor stream auto-topup stopped")

    async def _resolve_stream_id(self, vm: dict) -> Optional[int]:
        # Prefer local DB recorded stream_id
        sid = vm.get("config", {}).get("stream_id")
        if isinstance(sid, int):
            return sid
        # Ask provider for mapping
        try:
            provider_url = config.get_provider_url(vm["provider_ip"])
            async with ProviderClient(provider_url) as client:
                status = await client.get_vm_stream_status(vm["vm_id"])
                sid = status.get("stream_id")
                self._logger.debug(f"Resolved stream for VM {vm['name']}: {sid}")
                return int(sid) if sid is not None else None
        except Exception as e:
            self._logger.debug(f"Could not resolve stream for VM {vm['name']}: {e}")
            return None

    async def _run(self):
        interval = max(int(config.stream_monitor_interval_seconds), 5)
        min_remaining = max(int(config.stream_min_remaining_seconds), 0)
        target_seconds = max(int(config.stream_topup_target_seconds), min_remaining)
        while True:
            try:
                vms = await self.db.list_vms()
                self._logger.debug(f"stream monitor tick: {len(vms)} VMs to check")
                for vm in vms:
                    # Only manage running VMs
                    if vm.get("status") != "running":
                        self._logger.debug(f"skip VM {vm.get('name')} status={vm.get('status')}")
                        continue
                    stream_id = await self._resolve_stream_id(vm)
                    if stream_id is None:
                        self._logger.debug(f"skip VM {vm.get('name')} no stream mapped")
                        continue
                    # Read on-chain stream tuple via contract
                    try:
                        token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted = (
                            self._sp.contract.functions.streams(int(stream_id)).call()
                        )
                    except Exception as e:
                        self._logger.warning(f"stream lookup failed for {stream_id}: {e}")
                        continue
                    if bool(halted):
                        # Respect terminated streams
                        self._logger.debug(f"skip stream {stream_id} halted=true")
                        continue
                    # Compute remaining seconds using chain time
                    try:
                        now = int(self._sp.web3.eth.get_block("latest")["timestamp"])
                    except Exception as e:
                        self._logger.warning(f"could not get chain time: {e}")
                        continue
                    remaining = max(int(stopTime) - now, 0)
                    self._logger.debug(
                        f"VM {vm.get('name')} stream {stream_id}: remaining={remaining}s rate={int(ratePerSecond)}"
                    )
                    if remaining < min_remaining:
                        # Top up to reach target_seconds of runway
                        deficit = max(target_seconds - remaining, 0)
                        add_wei = int(deficit) * int(ratePerSecond)
                        if add_wei <= 0:
                            continue
                        try:
                            self._logger.info(
                                f"⛽ topping up stream {stream_id} by {add_wei} wei to reach {target_seconds}s"
                            )
                            self._sp.top_up(int(stream_id), int(add_wei))
                            self._logger.success(
                                f"topped up stream {stream_id} (+{add_wei} wei); VM={vm.get('name')}"
                            )
                        except Exception as e:
                            # Ignore failures; will retry next tick
                            self._logger.warning(f"top-up failed for stream {stream_id}: {e}")
                    else:
                        self._logger.debug(
                            f"stream {stream_id} healthy (remaining={remaining}s >= {min_remaining}s)"
                        )
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Keep the monitor resilient
                self._logger.error(f"requestor stream monitor error: {e}")
                await asyncio.sleep(interval)
