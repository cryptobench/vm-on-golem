import asyncio
from fastapi import FastAPI

from .utils.logging import setup_logger
from .vm.service import VMService
from .discovery.service import AdvertisementService
from .utils.pricing import PricingAutoUpdater

logger = setup_logger(__name__)


class ProviderService:
    """Service for managing the provider's lifecycle."""

    def __init__(self, vm_service: VMService, advertisement_service: AdvertisementService, port_manager):
        self.vm_service = vm_service
        self.advertisement_service = advertisement_service
        self.port_manager = port_manager
        self._pricing_updater: PricingAutoUpdater | None = None
        self._stream_monitor = None

    async def setup(self, app: FastAPI):
        """Setup and initialize the provider components."""
        from .config import settings
        from .utils.ascii_art import startup_animation
        from .security.faucet import FaucetClient

        try:
            # Display startup animation
            await startup_animation()

            logger.process("🔄 Initializing provider...")

            # Setup directories
            self._setup_directories()

            # Initialize services
            await self.port_manager.initialize()
            await self.vm_service.provider.initialize()

            # Before starting advertisement, sync allocated resources with existing VMs
            try:
                vm_resources = await self.vm_service.get_all_vms_resources()
                await self.vm_service.resource_tracker.sync_with_multipass(vm_resources)
            except Exception as e:
                logger.warning(f"Failed to sync resources with existing VMs: {e}")

            # Cross-check running VMs against payment streams. If a VM has no
            # active stream, it is no longer rented: terminate it and free resources.
            try:
                # Only perform checks if payments are configured
                if settings.STREAM_PAYMENT_ADDRESS and not settings.STREAM_PAYMENT_ADDRESS.lower().endswith("0000000000000000000000000000000000000000") and settings.POLYGON_RPC_URL:
                    stream_map = app.container.stream_map()
                    reader = app.container.stream_reader()

                    # Use the most recent view of VMs from the previous sync
                    vm_ids = list(vm_resources.keys()) if 'vm_resources' in locals() else []
                    for vm_id in vm_ids:
                        try:
                            stream_id = await stream_map.get(vm_id)
                        except Exception:
                            stream_id = None

                        if stream_id is None:
                            reason = "no stream mapped"
                            should_terminate = True
                        else:
                            try:
                                ok, msg = reader.verify_stream(int(stream_id), settings.PROVIDER_ID)
                                should_terminate = not ok
                                reason = msg if not ok else "ok"
                            except Exception as e:
                                # If verification cannot be performed, be conservative and keep the VM
                                logger.warning(f"Stream verification error for VM {vm_id} (stream {stream_id}): {e}")
                                should_terminate = False
                                reason = f"verification error: {e}"

                        if should_terminate:
                            logger.info(
                                f"Deleting VM {vm_id}: inactive stream (stream_id={stream_id}, reason={reason})"
                            )
                            try:
                                await self.vm_service.delete_vm(vm_id)
                            except Exception as e:
                                logger.warning(f"Failed to delete VM {vm_id}: {e}")
                            try:
                                await stream_map.remove(vm_id)
                            except Exception:
                                pass

                    # Re-sync after any terminations to ensure ads reflect capacity
                    try:
                        vm_resources = await self.vm_service.get_all_vms_resources()
                        await self.vm_service.resource_tracker.sync_with_multipass(vm_resources)
                    except Exception as e:
                        logger.warning(f"Post-termination resource sync failed: {e}")
                else:
                    logger.info("Payments not configured; skipping startup stream checks")
            except Exception as e:
                logger.warning(f"Failed to reconcile VMs with payment streams: {e}")

            await self.advertisement_service.start()
            # Start pricing auto-updater; trigger re-advertise after updates
            async def _on_price_updated(platform: str, glm_usd):
                await self.advertisement_service.trigger_update()
            self._pricing_updater = PricingAutoUpdater(on_updated_callback=_on_price_updated)
            asyncio.create_task(self._pricing_updater.start())

            # Start stream monitor if enabled
            from .container import Container
            from .config import settings as cfg
            if cfg.STREAM_MONITOR_ENABLED or cfg.STREAM_WITHDRAW_ENABLED:
                self._stream_monitor = app.container.stream_monitor()
                self._stream_monitor.start()

            # Check wallet balance and request funds if needed
            faucet_client = FaucetClient(
                faucet_url=settings.FAUCET_URL,
                captcha_url=settings.CAPTCHA_URL,
                captcha_api_key=settings.CAPTCHA_API_KEY,
            )
            await faucet_client.get_funds(settings.PROVIDER_ID)

            logger.success("✨ Provider setup complete")
        except Exception as e:
            logger.error(f"Startup failed: {e}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Cleanup provider components."""
        logger.process("🔄 Cleaning up provider...")
        await self.advertisement_service.stop()
        await self.vm_service.provider.cleanup()
        if self._pricing_updater:
            self._pricing_updater.stop()
        if self._stream_monitor:
            await self._stream_monitor.stop()
        logger.success("✨ Provider cleanup complete")

    def _setup_directories(self):
        """Create necessary directories for the provider."""
        from .config import settings
        from pathlib import Path
        
        Path(settings.VM_DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.SSH_KEY_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.CLOUD_INIT_DIR).mkdir(parents=True, exist_ok=True)
