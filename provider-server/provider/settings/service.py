import logging
from decimal import Decimal
from typing import Any

from provider.config_persistence import active_provider_env_path, write_env_vars
from provider.errors import ValidationError
from provider.live.events import ProviderEventBroadcaster
from provider.utils.pricing import fetch_glm_usd_price, usd_to_glm

from .domain import (
    PricingSettings,
    ProviderSettings,
    ResourceSettings,
    UpdatePricingSettings,
    UpdateResourceSettings,
)

logger = logging.getLogger(__name__)


class ProviderSettingsService:
    """Read and update provider settings used by desktop clients."""

    def __init__(
        self,
        settings: Any,
        resource_tracker: Any,
        broadcaster: ProviderEventBroadcaster | None = None,
        env_path_resolver=active_provider_env_path,
    ):
        self.settings = settings
        self.resource_tracker = resource_tracker
        self.broadcaster = broadcaster
        self.env_path_resolver = env_path_resolver

    async def get_settings(self, warning: str | None = None) -> ProviderSettings:
        detected = self._resources(
            getattr(
                self.resource_tracker,
                "detected_resources",
                self.resource_tracker.total_resources,
            )
        )
        offered = self._resources(self.resource_tracker.total_resources)
        allocated = self._resources(self.resource_tracker.allocated_resources)
        available = self._resources(self.resource_tracker.get_available_resources())
        minimum = self._minimum_configurable_resources(allocated)
        return ProviderSettings(
            detected_resources=detected,
            offered_resources=offered,
            allocated_resources=allocated,
            available_resources=available,
            minimum_configurable_resources=minimum,
            pricing=PricingSettings(
                usd_per_core_month=float(self._setting("PRICE_USD_PER_CORE_MONTH", 0)),
                usd_per_gb_ram_month=float(
                    self._setting("PRICE_USD_PER_GB_RAM_MONTH", 0)
                ),
                usd_per_gb_storage_month=float(
                    self._setting("PRICE_USD_PER_GB_STORAGE_MONTH", 0)
                ),
                glm_per_core_month=float(self._setting("PRICE_GLM_PER_CORE_MONTH", 0)),
                glm_per_gb_ram_month=float(
                    self._setting("PRICE_GLM_PER_GB_RAM_MONTH", 0)
                ),
                glm_per_gb_storage_month=float(
                    self._setting("PRICE_GLM_PER_GB_STORAGE_MONTH", 0)
                ),
                warning=warning,
            ),
        )

    async def update_resources(
        self, command: UpdateResourceSettings
    ) -> ProviderSettings:
        detected = self._resource_dict(
            getattr(
                self.resource_tracker,
                "detected_resources",
                self.resource_tracker.total_resources,
            )
        )
        allocated = self._resource_dict(self.resource_tracker.allocated_resources)
        requested = command.model_dump()

        for key, value in requested.items():
            if value > detected[key]:
                raise ValidationError(
                    f"{key} cannot exceed detected hardware ({detected[key]})"
                )
            if value < allocated[key]:
                raise ValidationError(
                    f"{key} cannot be below currently allocated resources ({allocated[key]})"
                )

        write_env_vars(
            self.env_path_resolver(),
            {
                "GOLEM_PROVIDER_OFFERED_CPU_CORES": command.cpu,
                "GOLEM_PROVIDER_OFFERED_MEMORY_GB": command.memory,
                "GOLEM_PROVIDER_OFFERED_STORAGE_GB": command.storage,
            },
        )
        self._set_setting("OFFERED_CPU_CORES", command.cpu)
        self._set_setting("OFFERED_MEMORY_GB", command.memory)
        self._set_setting("OFFERED_STORAGE_GB", command.storage)

        if hasattr(self.resource_tracker, "set_offered_resources"):
            await self.resource_tracker.set_offered_resources(requested)
        else:
            self.resource_tracker.total_resources = requested

        await self._publish_summary()
        return await self.get_settings()

    async def update_pricing(self, command: UpdatePricingSettings) -> ProviderSettings:
        write_env_vars(
            self.env_path_resolver(),
            {
                "GOLEM_PROVIDER_PRICE_USD_PER_CORE_MONTH": command.usd_per_core_month,
                "GOLEM_PROVIDER_PRICE_USD_PER_GB_RAM_MONTH": command.usd_per_gb_ram_month,
                "GOLEM_PROVIDER_PRICE_USD_PER_GB_STORAGE_MONTH": command.usd_per_gb_storage_month,
            },
        )
        self._set_setting("PRICE_USD_PER_CORE_MONTH", command.usd_per_core_month)
        self._set_setting("PRICE_USD_PER_GB_RAM_MONTH", command.usd_per_gb_ram_month)
        self._set_setting(
            "PRICE_USD_PER_GB_STORAGE_MONTH", command.usd_per_gb_storage_month
        )

        warning = None
        glm_usd = fetch_glm_usd_price()
        if glm_usd:
            self._set_setting(
                "PRICE_GLM_PER_CORE_MONTH",
                float(usd_to_glm(Decimal(str(command.usd_per_core_month)), glm_usd)),
            )
            self._set_setting(
                "PRICE_GLM_PER_GB_RAM_MONTH",
                float(usd_to_glm(Decimal(str(command.usd_per_gb_ram_month)), glm_usd)),
            )
            self._set_setting(
                "PRICE_GLM_PER_GB_STORAGE_MONTH",
                float(
                    usd_to_glm(Decimal(str(command.usd_per_gb_storage_month)), glm_usd)
                ),
            )
        else:
            warning = "Could not fetch GLM/USD; GLM estimates were not recalculated."

        await self._publish_summary()
        return await self.get_settings(warning=warning)

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        value = getattr(self.settings, name, default)
        if value is default:
            return default
        try:
            return value()
        except Exception:
            return value

    def _set_setting(self, name: str, value: Any) -> None:
        if isinstance(self.settings, dict):
            self.settings[name] = value
            return
        option = getattr(self.settings, name, None)
        if hasattr(option, "from_value"):
            option.from_value(value)
        else:
            try:
                setattr(self.settings, name, value)
            except Exception:
                logger.debug("Unable to set provider setting %s", name, exc_info=True)

    @staticmethod
    def _resource_dict(value: Any) -> dict[str, int]:
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        return {
            "cpu": int(value.get("cpu", 0)),
            "memory": int(value.get("memory", 0)),
            "storage": int(value.get("storage", 0)),
        }

    @classmethod
    def _resources(cls, value: Any) -> ResourceSettings:
        return ResourceSettings(**cls._resource_dict(value))

    @staticmethod
    def _minimum_configurable_resources(
        allocated: ResourceSettings,
    ) -> ResourceSettings:
        return ResourceSettings(
            cpu=max(1, allocated.cpu),
            memory=max(1, allocated.memory),
            storage=max(1, allocated.storage),
        )

    async def _publish_summary(self) -> None:
        if self.broadcaster is not None:
            await self.broadcaster.publish(["summary"])
