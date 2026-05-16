from typing import Any

from pydantic import BaseModel, Field


class CreateStreamCommand(BaseModel):
    provider_address: str = Field(..., min_length=1)
    deposit_wei: int = Field(..., ge=1)
    rate_per_second_wei: int = Field(..., ge=1)
    lease_id: str = Field(..., min_length=1)
    terms_hash: str = Field(..., min_length=1)
    quote_expires_at: int = Field(..., ge=1)
    provider_signature: str = Field(..., min_length=1)


class TopUpStreamCommand(BaseModel):
    amount_wei: int = Field(..., ge=1)


class StreamActionResult(BaseModel):
    stream_id: int | None = None
    transaction_hash: str | None = None
    status: str = "submitted"
    details: dict[str, Any] | None = None


class VMStreamStatus(BaseModel):
    vm_name: str
    vm_id: str
    stream_id: int | None = None
    provider_ip: str
    status: str
