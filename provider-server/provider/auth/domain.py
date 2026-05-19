from pydantic import BaseModel, Field


class RequestorIdentity(BaseModel):
    requestor_address: str
    vm_id: str
    token_id: str
    expires_at: int
    scope: str = "vm"
    is_admin: bool = False


class AdminIdentity(BaseModel):
    token_id: str = "provider-admin"


class RequestorSessionCommand(BaseModel):
    requestor_address: str
    vm_id: str | None = Field(default=None, min_length=3, max_length=64)
    nonce: str = Field(..., min_length=8, max_length=128)
    deadline: int
    signature: str
    scope: str = "vm"


class RequestorSession(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    requestor_address: str
    vm_id: str | None = None
    scope: str = "vm"
