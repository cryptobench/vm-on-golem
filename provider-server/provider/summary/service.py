import logging
from typing import Any

from provider.errors import ExternalServiceError

from .domain import ProviderSummary

logger = logging.getLogger(__name__)


class ProviderSummaryService:
    """Build concise provider summary for GUI clients."""

    def __init__(
        self,
        settings: Any,
        resource_tracker: Any,
        vm_service: Any,
        certificate_service: Any = None,
    ):
        self.settings = settings
        self.resource_tracker = resource_tracker
        self.vm_service = vm_service
        self.certificate_service = certificate_service

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    async def get_summary(self) -> ProviderSummary:
        try:
            vms = await self._vm_summaries()
            return ProviderSummary(
                status="running",
                resources={
                    "total": self.resource_tracker.total_resources,
                    "available": self.resource_tracker.get_available_resources(),
                },
                pricing={
                    "usd_per_core_month": float(
                        self._setting("PRICE_USD_PER_CORE_MONTH", 0)
                    ),
                    "usd_per_gb_ram_month": float(
                        self._setting("PRICE_USD_PER_GB_RAM_MONTH", 0)
                    ),
                    "usd_per_gb_storage_month": float(
                        self._setting("PRICE_USD_PER_GB_STORAGE_MONTH", 0)
                    ),
                    "glm_per_core_month": float(
                        self._setting("PRICE_GLM_PER_CORE_MONTH", 0)
                    ),
                    "glm_per_gb_ram_month": float(
                        self._setting("PRICE_GLM_PER_GB_RAM_MONTH", 0)
                    ),
                    "glm_per_gb_storage_month": float(
                        self._setting("PRICE_GLM_PER_GB_STORAGE_MONTH", 0)
                    ),
                },
                vms=vms,
                env={
                    "environment": self._setting("ENVIRONMENT", None),
                    "network": self._setting("NETWORK", None),
                },
                certificate=self._certificate_status(),
            )
        except Exception as exc:
            logger.error("summary collection failed", exc_info=True)
            raise ExternalServiceError("failed to collect summary") from exc

    async def _vm_summaries(self) -> list[dict]:
        items = await self.vm_service.list_vms()
        return [
            {
                "id": vm.id,
                "status": vm.status.value
                if hasattr(vm.status, "value")
                else str(vm.status),
                "ssh_port": vm.ssh_port,
                "resources": {
                    "cpu": vm.resources.cpu,
                    "memory": vm.resources.memory,
                    "storage": vm.resources.storage,
                },
            }
            for vm in items
        ]

    def _certificate_status(self):
        if self.certificate_service is None:
            return None
        return self.certificate_service.get_status()
