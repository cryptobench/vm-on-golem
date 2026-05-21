from pydantic import BaseModel


class LeasePayment(BaseModel):
    stream_id: int
    lease_id: str
    terms_hash: str
    provider_rate_per_second_wei: int
    duration_seconds: int | None = None


class LeaseQuoteCommand(BaseModel):
    vm_name: str
    image: str | None = None
    cpu: int
    memory: int
    storage: int
    duration_seconds: int
    requestor_address: str


class LeaseQuote(BaseModel):
    provider_address: str
    chain_id: int
    contract_address: str
    glm_token_address: str
    lease_id: str
    terms_hash: str
    provider_rate_per_second_wei: int
    provider_deposit_wei: int
    min_runway_seconds: int
    quote_expires_at: int
    signature: str


class StreamOnChain(BaseModel):
    token: str
    sender: str
    recipient: str
    startTime: int
    stopTime: int
    providerRatePerSecond: int
    providerDeposit: int
    providerWithdrawn: int
    donationBps: int
    donationRecipient: str
    donationDeposit: int
    donationWithdrawn: int
    leaseId: str
    termsHash: str


class StreamComputed(BaseModel):
    now: int
    remaining_seconds: int
    vested_wei: int
    withdrawable_wei: int
    provider_vested_wei: int
    provider_withdrawable_wei: int
    donation_vested_wei: int
    donation_withdrawable_wei: int
    total_deposit_wei: int


class StreamStatus(BaseModel):
    vm_id: str
    stream_id: int
    chain: StreamOnChain
    computed: StreamComputed
    verified: bool
    reason: str
    payment_state: str = "unknown"
