import asyncio

from fastapi import FastAPI

from .discovery.publishing_service import DiscoveryPublishingService
from .utils.logging import setup_logger
from .utils.pricing import PricingAutoUpdater
from .vm.service import VMService

logger = setup_logger(__name__)


class ProviderService:
    """Service for managing the provider's lifecycle."""

    def __init__(
        self,
        vm_service: VMService,
        advertisement_service: DiscoveryPublishingService,
        port_manager,
        monitoring_service=None,
        network_setup_service=None,
        stream_payment_event_service=None,
    ):
        self.vm_service = vm_service
        self.advertisement_service = advertisement_service
        self.port_manager = port_manager
        self.monitoring_service = monitoring_service
        self.network_setup_service = network_setup_service
        self.stream_payment_event_service = stream_payment_event_service
        self._pricing_updater: PricingAutoUpdater | None = None
        self._pricing_task: asyncio.Task | None = None
        self._stream_monitor = None

    async def setup(self, app: FastAPI):
        """Setup and initialize the provider components."""
        from .config import settings
        from .utils.ascii_art import provider_ready_message, startup_animation

        try:
            logger.process("🔄 Initializing provider...")

            # Setup directories
            self._setup_directories()
            logger.info("Provider directories ready")

            if self.network_setup_service is not None:
                logger.info("Starting provider network setup")
                await self.network_setup_service.setup()
                if hasattr(self.network_setup_service, "start_certificate_maintenance"):
                    await self.network_setup_service.start_certificate_maintenance()
                logger.info("Provider network setup complete")
            else:
                logger.info("Provider network setup service not configured")

            # Display service startup animation only after strict network setup passes.
            await startup_animation()

            # Initialize services
            port_ok = await self.port_manager.initialize()
            if port_ok is False:
                raise RuntimeError("No externally reachable VM access ports")
            logger.info("Provider port manager initialized")
            await self.vm_service.provider.initialize()
            logger.info("Provider VM backend initialized")

            # Before starting advertisement, sync allocated resources with existing VMs
            try:
                vm_resources = await self.vm_service.get_all_vms_resources()
                await self.vm_service.resource_tracker.sync_with_multipass(vm_resources)
                logger.info(
                    "Provider resources synced with existing VMs",
                    extra={"vm_count": len(vm_resources)},
                )
            except Exception as e:
                logger.warning(f"Failed to sync resources with existing VMs: {e}")

            # Cross-check running VMs against payment streams. Stream state is
            # authoritative: only a chain-confirmed terminated stream may cause
            # local VM deletion.
            try:
                # Only perform checks if payments are configured
                if (
                    settings.STREAM_PAYMENT_ADDRESS
                    and not settings.STREAM_PAYMENT_ADDRESS.lower().endswith(
                        "0000000000000000000000000000000000000000"
                    )
                    and settings.PAYMENTS_RPC_URL
                ):
                    stream_map = app.container.stream_map()
                    reader = app.container.stream_reader()
                    active_items = await stream_map.active_items()
                    records = await stream_map.records()

                    # Use the most recent view of VMs from the previous sync
                    vm_ids = (
                        list(vm_resources.keys()) if "vm_resources" in locals() else []
                    )
                    for vm_id in vm_ids:
                        if vm_id not in active_items:
                            record = records.get(vm_id)
                            if record and record.get("state") == "terminated":
                                continue
                            raise RuntimeError(
                                f"VM {vm_id} has no active structured stream record"
                            )

                    for vm_id, stream_id in active_items.items():
                        try:
                            stream = reader.get_stream(int(stream_id))
                        except Exception as e:
                            raise RuntimeError(
                                f"stream lookup failed for VM {vm_id} "
                                f"(stream_id={stream_id}): {e}"
                            ) from e

                        if (
                            str(stream.get("recipient", "")).lower()
                            != "0x0000000000000000000000000000000000000000"
                        ):
                            continue

                        logger.info(
                            "Deleting VM after startup found terminated stream",
                            extra={"vm_id": vm_id, "stream_id": int(stream_id)},
                        )
                        await stream_map.mark_terminated(
                            vm_id,
                            terminated_by="requestor",
                            termination_reason="requestor_terminated",
                            settlement_tx_hash=None,
                            cleanup_state="not_started",
                        )
                        try:
                            await self.vm_service.delete_vm(vm_id)
                        except Exception as e:
                            await stream_map.set_cleanup_state(vm_id, "failed")
                            raise RuntimeError(
                                f"failed to delete VM {vm_id} after stream "
                                f"termination: {e}"
                            ) from e
                        await stream_map.set_cleanup_state(vm_id, "completed")

                    # Re-sync after any terminations to ensure ads reflect capacity
                    try:
                        vm_resources = await self.vm_service.get_all_vms_resources()
                        await self.vm_service.resource_tracker.sync_with_multipass(
                            vm_resources
                        )
                    except Exception as e:
                        raise RuntimeError(
                            f"post-termination resource sync failed: {e}"
                        ) from e
                else:
                    logger.info(
                        "Payments not configured; skipping startup stream checks"
                    )
            except Exception as e:
                logger.error(
                    "Failed to reconcile VMs with payment streams", exc_info=True
                )
                raise

            await self.advertisement_service.start()
            logger.info("Provider discovery publishing started")
            if self.monitoring_service is not None:
                await self.monitoring_service.start()
                logger.info("Provider monitoring service started")
            # Start pricing auto-updater; trigger re-advertise after updates
            async def _on_price_updated(platform: str, glm_usd):
                await self.advertisement_service.trigger_update()

            self._pricing_updater = PricingAutoUpdater(
                on_updated_callback=_on_price_updated
            )
            # Keep a handle to the background task so we can cancel it promptly on shutdown
            self._pricing_task = asyncio.create_task(
                self._pricing_updater.start(), name="pricing-updater"
            )
            logger.info("Provider pricing updater started")

            # Start stream monitor if enabled
            from .config import settings as cfg
            from .container import Container

            if cfg.STREAM_MONITOR_ENABLED or cfg.STREAM_WITHDRAW_ENABLED:
                self._stream_monitor = app.container.stream_monitor()
                self._stream_monitor.start()
                logger.info("Provider stream monitor started")

            if self.stream_payment_event_service is not None:
                self.stream_payment_event_service.start()
                logger.info("Provider StreamPayment event service started")

            await provider_ready_message(int(settings.PORT))
            logger.success("✨ Provider setup complete")
        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)
            await self.cleanup()
            raise

    async def cleanup(self):
        """Cleanup provider components."""
        logger.process("🔄 Cleaning up provider...")
        from .config import settings

        # Stop advertising loop
        try:
            if self.network_setup_service is not None:
                await self.network_setup_service.cleanup()
                logger.info("Provider network setup service stopped")
        except Exception as e:
            logger.warning(f"Provider network setup cleanup failed: {e}", exc_info=True)

        # Stop advertising loop
        try:
            if self.monitoring_service is not None:
                await self.monitoring_service.stop()
                logger.info("Provider monitoring service stopped")
        except Exception as e:
            logger.warning(f"Provider monitoring cleanup failed: {e}", exc_info=True)

        # Stop advertising loop
        try:
            await self.advertisement_service.stop()
            logger.info("Provider discovery publishing stopped")
        except Exception as e:
            logger.warning(f"Provider discovery cleanup failed: {e}", exc_info=True)

        # Optionally stop all running VMs based on configuration (default: keep running)
        try:
            if bool(getattr(settings, "STOP_VMS_ON_EXIT", False)):
                try:
                    vms = await self.vm_service.list_vms()
                except Exception as e:
                    logger.warning(
                        f"Failed to list VMs during provider cleanup: {e}",
                        exc_info=True,
                    )
                    vms = []
                for vm in vms:
                    try:
                        await self.vm_service.stop_vm(vm.id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to stop VM {getattr(vm, 'id', '?')}: {e}"
                        )
        except Exception as e:
            logger.warning(f"Provider VM shutdown cleanup failed: {e}", exc_info=True)

        # Provider cleanup hook
        try:
            await self.vm_service.provider.cleanup()
            logger.info("Provider VM backend cleanup complete")
        except Exception as e:
            logger.warning(f"Provider VM backend cleanup failed: {e}", exc_info=True)

        # Stop pricing updater promptly (cancel background task and set stop flag)
        if self._pricing_updater:
            try:
                self._pricing_updater.stop()
                logger.info("Provider pricing updater stop requested")
            except Exception as e:
                logger.warning(
                    f"Provider pricing updater stop failed: {e}", exc_info=True
                )
        if self._pricing_task:
            try:
                self._pricing_task.cancel()
                await self._pricing_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(
                    f"Provider pricing task cleanup failed: {e}", exc_info=True
                )
        if self._stream_monitor:
            await self._stream_monitor.stop()
            logger.info("Provider stream monitor stopped")
        if self.stream_payment_event_service is not None:
            await self.stream_payment_event_service.stop()
            logger.info("Provider StreamPayment event service stopped")
        logger.success("✨ Provider cleanup complete")

    def _setup_directories(self):
        """Create necessary directories for the provider."""
        from pathlib import Path

        from .config import settings

        Path(settings.VM_DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.SSH_KEY_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.CLOUD_INIT_DIR).mkdir(parents=True, exist_ok=True)
