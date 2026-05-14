from typing import Any

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
        endpoint_port = int(self._setting("PUBLIC_HTTPS_PORT", 443) or 443)
        endpoint_url = None
        if ip_address:
            endpoint_url = (
                f"https://{ip_address}"
                if endpoint_port == 443
                else f"https://{ip_address}:{endpoint_port}"
            )
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
