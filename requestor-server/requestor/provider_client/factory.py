from requestor.config import RequestorConfig
from requestor.provider.client import ProviderClient


class ProviderClientFactory:
    def __init__(self, settings: RequestorConfig):
        self.settings = settings

    def for_provider_ip(self, provider_ip: str) -> ProviderClient:
        return ProviderClient(self.settings.get_provider_url(provider_ip))

    def for_provider_endpoint(
        self, provider_ip: str, endpoint_url: str | None = None
    ) -> ProviderClient:
        return ProviderClient(self.settings.get_provider_url(provider_ip, endpoint_url))
