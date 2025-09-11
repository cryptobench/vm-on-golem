import asyncio
from typing import Optional

from golem_base_sdk import (
    GolemBaseClient,
    GolemBaseCreate,
    GolemBaseUpdate,
    GolemBaseDelete,
    Annotation,
    GolemBaseExtend,
)
from .advertiser import Advertiser
from .golem_base_utils import get_provider_entity_keys
from ..config import settings
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class GolemBaseAdvertiser(Advertiser):
    """Advertise available resources to the Golem Base network."""

    def __init__(self, resource_tracker: "ResourceTracker"):
        self.resource_tracker = resource_tracker
        self.client: Optional[GolemBaseClient] = None
        self._stop_event = asyncio.Event()

    async def initialize(self):
        """Initialize the advertiser."""
        private_key_hex = settings.ETHEREUM_PRIVATE_KEY.replace("0x", "")
        private_key_bytes = bytes.fromhex(private_key_hex)
        self.client = await GolemBaseClient.create(
            rpc_url=settings.GOLEM_BASE_RPC_URL,
            ws_url=settings.GOLEM_BASE_WS_URL,
            private_key=private_key_bytes,
        )
        self.resource_tracker.on_update(
            lambda: asyncio.create_task(self.post_advertisement())
        )

    async def start_loop(self):
        """Start advertising resources in a loop."""
        try:
            while not self._stop_event.is_set():
                await self.post_advertisement()
                # Check more frequently than full TTL to ensure seamless renewal
                interval = max(30, int(settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL // 3))
                await asyncio.sleep(interval)
        finally:
            await self.stop()

    async def stop(self):
        """Stop advertising resources."""
        self._stop_event.set()
        if self.client:
            await self.client.disconnect()

    async def post_advertisement(self):
        """Post or update resource advertisement on the Golem Base network."""
        if not self.client:
            raise RuntimeError("Golem Base client not initialized")

        resources = self.resource_tracker.get_available_resources()
        if not self.resource_tracker._meets_minimum_requirements(resources):
            logger.warning("Resources too low, skipping advertisement")
            return

        ip_address = settings.PUBLIC_IP
        if not ip_address:
            logger.error("Could not get public IP, skipping advertisement")
            return

        try:
            existing_keys = await get_provider_entity_keys(self.client, settings.PROVIDER_ID)

            # String annotations (metadata + prices as strings; on-chain numeric annotations must be ints)
            import platform as _plat
            raw = (_plat.machine() or '').lower()
            platform_str = None
            if raw:
                if 'aarch64' in raw or 'arm64' in raw or raw.startswith('arm'):
                    platform_str = 'arm64'
                elif 'x86_64' in raw or 'amd64' in raw or 'x64' in raw:
                    platform_str = 'x86_64'
                else:
                    platform_str = raw
            string_annotations = [
                Annotation(key="golem_type", value="provider"),
                Annotation(key="golem_network", value=settings.NETWORK),
                Annotation(key="golem_payments_network", value=settings.PAYMENTS_NETWORK),
                Annotation(key="golem_provider_id", value=settings.PROVIDER_ID),
                Annotation(key="golem_ip_address", value=ip_address),
                Annotation(key="golem_country", value=settings.PROVIDER_COUNTRY),
                Annotation(key="golem_provider_name", value=settings.PROVIDER_NAME),
                Annotation(key="golem_platform", value=platform_str or ""),
                Annotation(key="golem_price_currency", value="USD/GLM"),
                # Prices must be strings to avoid RLP sedes errors (ints only allowed for numeric annotations)
                Annotation(key="golem_price_usd_core_month", value=str(float(settings.PRICE_USD_PER_CORE_MONTH))),
                Annotation(key="golem_price_usd_ram_gb_month", value=str(float(settings.PRICE_USD_PER_GB_RAM_MONTH))),
                Annotation(key="golem_price_usd_storage_gb_month", value=str(float(settings.PRICE_USD_PER_GB_STORAGE_MONTH))),
                Annotation(key="golem_price_glm_core_month", value=str(float(settings.PRICE_GLM_PER_CORE_MONTH))),
                Annotation(key="golem_price_glm_ram_gb_month", value=str(float(settings.PRICE_GLM_PER_GB_RAM_MONTH))),
                Annotation(key="golem_price_glm_storage_gb_month", value=str(float(settings.PRICE_GLM_PER_GB_STORAGE_MONTH))),
            ]
            # Numeric annotations: strictly integers
            numeric_annotations = [
                Annotation(key="golem_cpu", value=resources["cpu"]),
                Annotation(key="golem_memory", value=resources["memory"]),
                Annotation(key="golem_storage", value=resources["storage"]),
            ]

            if len(existing_keys) > 1:
                logger.warning(f"Found {len(existing_keys)} advertisements. Cleaning up and creating a new one.")
                deletes = [GolemBaseDelete(entity_key=key) for key in existing_keys]
                await self.client.delete_entities(deletes)
                await self._create_advertisement(string_annotations, numeric_annotations)

            elif len(existing_keys) == 1:
                entity_key = existing_keys[0]
                metadata = await self.client.get_entity_metadata(entity_key)
                
                current_annotations = {ann.key: ann.value for ann in metadata.numeric_annotations}
                current_annotations.update({ann.key: ann.value for ann in metadata.string_annotations})

                # Full comparison of all annotations
                expected_annotations = {ann.key: ann.value for ann in string_annotations}
                expected_annotations.update({ann.key: ann.value for ann in numeric_annotations})

                # Debugging logs to compare annotations
                logger.info(f"IP address from settings: {ip_address}")
                logger.info(f"Current on-chain annotations: {current_annotations}")
                logger.info(f"Expected annotations based on current config: {expected_annotations}")

                desired_btl_blocks = int(settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL) * 2  # ~2 blocks/sec

                if sorted(current_annotations.items()) == sorted(expected_annotations.items()):
                    # Refresh TTL proactively if nearing expiry
                    try:
                        current_block = await self.client.http_client().eth.get_block_number()
                        remaining_blocks = int(metadata.expires_at_block) - int(current_block)
                    except Exception:
                        # If we cannot determine remaining blocks, extend defensively
                        remaining_blocks = 0

                    # Refresh when below 20% of desired TTL (or if unknown/negative)
                    refresh_threshold = max(10, desired_btl_blocks // 5)
                    if remaining_blocks <= refresh_threshold:
                        logger.info(
                            f"Extending advertisement TTL (remaining_blocks={remaining_blocks}, threshold={refresh_threshold})."
                        )
                        ext = GolemBaseExtend(entity_key=entity_key, number_of_blocks=desired_btl_blocks)
                        await self.client.extend_entities([ext])
                        logger.info(f"Extended advertisement. Entity key: {entity_key}")
                    else:
                        logger.info(
                            f"Advertisement up-to-date; TTL sufficient (remaining_blocks={remaining_blocks})."
                        )
                else:
                    logger.info("Advertisement is outdated. Updating.")
                    update = GolemBaseUpdate(
                        entity_key=entity_key,
                        data=b"",
                        btl=desired_btl_blocks,
                        string_annotations=string_annotations,
                        numeric_annotations=numeric_annotations,
                    )
                    await self.client.update_entities([update])
                    logger.info(f"Updated advertisement. Entity key: {entity_key}")

            else: # No existing keys
                await self._create_advertisement(string_annotations, numeric_annotations)

        except Exception as e:
            logger.error(f"Failed to post or update advertisement on Golem Base: {e}")

    async def _create_advertisement(self, string_annotations, numeric_annotations):
        """Helper to create a new advertisement."""
        desired_btl_blocks = int(settings.GOLEM_BASE_ADVERTISEMENT_INTERVAL) * 2  # ~2 blocks/sec
        entity = GolemBaseCreate(
            data=b"",
            btl=desired_btl_blocks,
            string_annotations=string_annotations,
            numeric_annotations=numeric_annotations,
        )
        receipts = await self.client.create_entities([entity])
        if receipts:
            receipt = receipts[0]
            logger.info(f"Posted new advertisement. Entity key: {receipt.entity_key}")
        else:
            logger.error("Failed to post advertisement: no receipt received")
