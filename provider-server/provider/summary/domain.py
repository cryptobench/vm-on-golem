from pydantic import BaseModel


class ProviderSummary(BaseModel):
    status: str
    resources: dict
    pricing: dict
    vms: list[dict]
    env: dict
