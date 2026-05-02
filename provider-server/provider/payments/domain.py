from pydantic import BaseModel


class StreamOnChain(BaseModel):
    token: str
    sender: str
    recipient: str
    startTime: int
    stopTime: int
    ratePerSecond: int
    deposit: int
    withdrawn: int
    halted: bool


class StreamComputed(BaseModel):
    now: int
    remaining_seconds: int
    vested_wei: int
    withdrawable_wei: int


class StreamStatus(BaseModel):
    vm_id: str
    stream_id: int
    chain: StreamOnChain
    computed: StreamComputed
    verified: bool
    reason: str
