from pydantic import BaseModel

from provider.network_setup.domain import CertificateStatus


class ProviderSummary(BaseModel):
    status: str
    resources: dict
    pricing: dict
    vms: list[dict]
    env: dict
    certificate: CertificateStatus | None = None
