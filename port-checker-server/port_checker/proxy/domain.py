from typing import Optional

from pydantic import BaseModel


class ProviderProxyCommand(BaseModel):
    method: str
    provider_id: str
    path: str
    query: str
    headers: dict[str, str]
    body: bytes
    client_host: str
    port: int
    source: Optional[str]
    token: Optional[str]
    arkiv_rpc_url: Optional[str]
    arkiv_ws_url: Optional[str]


class DirectProxyCommand(BaseModel):
    method: str
    path: str
    query: str
    headers: dict[str, str]
    body: bytes
    client_host: str
    forward_to: Optional[str]
    protocol: Optional[str]
    token: Optional[str]
    target: Optional[str]


class ProxyResponse(BaseModel):
    content: bytes
    status_code: int
    headers: dict[str, str]
