from typing import Any

from provider.discovery.publishers import _provider_endpoint
from provider.platform import current_platform

from .domain import ProviderInfo


class ProviderInfoService:
    """Build provider metadata exposed to requestors."""

    def __init__(self, settings: Any):
        self.settings = settings

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def get_info(self) -> ProviderInfo:
        glm_token = str(self._setting("GLM_TOKEN_ADDRESS", "") or "")
        ip_address = self._setting("PUBLIC_IP", None)
        endpoint_url = None
        if ip_address:
            _, _, _, endpoint_url = _provider_endpoint(self.settings, str(ip_address))
        return ProviderInfo(
            provider_id=str(self._setting("PROVIDER_ID", "") or ""),
            stream_payment_address=str(
                self._setting("STREAM_PAYMENT_ADDRESS", "") or ""
            ),
            glm_token_address=glm_token,
            eth_token_address=glm_token,
            ip_address=ip_address,
            endpoint_url=endpoint_url,
            country=self._setting("PROVIDER_COUNTRY", None),
            platform=current_platform(),
        )
