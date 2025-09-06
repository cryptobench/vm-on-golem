import asyncio
from fastapi import FastAPI

from .utils.logging import setup_logger
from .vm.service import VMService
from .discovery.service import AdvertisementService

logger = setup_logger(__name__)


class ProviderService:
    """Service for managing the provider's lifecycle."""

    def __init__(self, vm_service: VMService, advertisement_service: AdvertisementService, port_manager):
        self.vm_service = vm_service
        self.advertisement_service = advertisement_service
        self.port_manager = port_manager

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
            await self.advertisement_service.start()

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
        logger.success("✨ Provider cleanup complete")

    def _setup_directories(self):
        """Create necessary directories for the provider."""
        from .config import settings
        from pathlib import Path
        
        Path(settings.VM_DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.SSH_KEY_DIR).mkdir(parents=True, exist_ok=True)
        Path(settings.CLOUD_INIT_DIR).mkdir(parents=True, exist_ok=True)
