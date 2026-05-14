from pydantic import BaseModel


class ProviderInfo(BaseModel):
    provider_id: str
    stream_payment_address: str
    glm_token_address: str
    eth_token_address: str
    ip_address: str | None = None
    endpoint_url: str | None = None
    country: str | None = None
    platform: str | None = None
