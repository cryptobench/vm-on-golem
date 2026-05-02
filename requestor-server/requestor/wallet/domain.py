from pydantic import BaseModel


class FaucetResult(BaseModel):
    address: str
    status: str
    transaction_hash: str | None = None
