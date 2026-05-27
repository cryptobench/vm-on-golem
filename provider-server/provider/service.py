import asyncio

from fastapi import FastAPI

from .discovery.publishing_service import DiscoveryPublishingService
from .network.location_resolver import ensure_provider_location
from .payments.stream_status_service import (
    EXPIRED_PAYMENT_STATE,
    STREAM_GRACE_PERIOD_SECONDS,
    TERMINATED_PAYMENT_STATE,
)
from .utils.logging import setup_logger
from .utils.pricing import PricingAutoUpdater
from .vm.models import VMNotFoundError
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
            logger.process("Initializing provider...")

            location = await ensure_provider_location(settings)
            self._sync_runtime_settings_to_container(app, settings)
            logger.info(
                "Provider public location resolved",
                extra={
                    "ip_address": location.ip_address,
                    "country": location.country,
                },
            )

            # Setup directories
            self._setup_directories()
            logger.info("Provider directories ready")

            if self.network_setup_service is not None:
                logger.info("Starting provider network setup")
                await self.network_setup_service.setup()
                self._sync_runtime_settings_to_container(app, settings)
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
                            logger.error(
                                "Startup stream lookup failed; keeping provider "
                                "online with the VM counted as allocated capacity",
                                extra={
                                    "vm_id": vm_id,
                                    "stream_id": int(stream_id),
                                    "error": str(e),
                                },
                                exc_info=True,
                            )
                            continue

                        payment_state = self._startup_stream_state(
                            reader, int(stream_id), stream
                        )
                        if payment_state not in {
                            TERMINATED_PAYMENT_STATE,
                            EXPIRED_PAYMENT_STATE,
                        }:
                            continue

                        logger.info(
                            "Deleting VM after startup found ended stream",
                            extra={
                                "vm_id": vm_id,
                                "stream_id": int(stream_id),
                                "payment_state": payment_state,
                            },
                        )
                        await stream_map.mark_terminated(
                            vm_id,
                            terminated_by=(
                                "requestor"
                                if payment_state == TERMINATED_PAYMENT_STATE
                                else "provider"
                            ),
                            termination_reason=(
                                "requestor_terminated"
                                if payment_state == TERMINATED_PAYMENT_STATE
                                else "stream_expired"
                            ),
                            settlement_tx_hash=None,
                            cleanup_state="not_started",
                        )
                        try:
                            await self.vm_service.delete_vm(vm_id)
                        except VMNotFoundError:
                            logger.warning(
                                "VM already missing after startup found ended stream; "
                                "marking cleanup complete",
                                extra={
                                    "vm_id": vm_id,
                                    "stream_id": int(stream_id),
                                    "payment_state": payment_state,
                                },
                            )
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
            logger.success("Provider setup complete")
        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)
            await self.cleanup()
            raise

    @staticmethod
    def _startup_stream_state(reader, stream_id: int, stream: dict) -> str:
        stream_state = getattr(reader, "stream_state", None)
        state_lookup_error: Exception | None = None
        if stream_state is not None:
            try:
                return str(stream_state(stream_id)).lower()
            except Exception:
                state_lookup_error = RuntimeError(
                    f"payment stream state lookup failed for stream {stream_id}"
                )
                logger.warning(
                    "Payment stream state lookup failed; deriving state from stream data",
                    extra={"stream_id": stream_id},
                    exc_info=True,
                )
        if (
            str(stream.get("recipient", "")).lower()
            == "0x0000000000000000000000000000000000000000"
        ):
            return TERMINATED_PAYMENT_STATE
        web3 = getattr(reader, "web3", None)
        eth = getattr(web3, "eth", None)
        get_block = getattr(eth, "get_block", None)
        if get_block is None:
            if state_lookup_error is not None:
                raise state_lookup_error
            return "active"
        now = int(get_block("latest")["timestamp"])
        if now >= int(stream["stopTime"]) + STREAM_GRACE_PERIOD_SECONDS:
            return EXPIRED_PAYMENT_STATE
        return "active"

    async def cleanup(self):
        """Cleanup provider components."""
        logger.process("Cleaning up provider...")
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
        logger.success("Provider cleanup complete")

    def _setup_directories(self):
        """Create necessary directories for the provider."""
        from pathlib import Path

        from .config import settings

        Path(settings.VM_DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.SSH_KEY_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.CLOUD_INIT_DIR).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sync_runtime_settings_to_container(app: FastAPI, settings) -> None:
        container = getattr(app, "container", None)
        config = getattr(container, "config", None)
        if config is not None and hasattr(config, "from_dict"):
            config.from_dict(settings.model_dump())
