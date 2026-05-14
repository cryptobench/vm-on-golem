from requestor.config import RequestorConfig
from requestor.provider.client import ProviderClient


class ProviderClientFactory:
    def __init__(self, settings: RequestorConfig):
        self.settings = settings

    def for_provider_endpoint(self, endpoint_url: str | None = None) -> ProviderClient:
        return ProviderClient(self.settings.get_provider_url(endpoint_url))
