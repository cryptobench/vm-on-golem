import pytest

from provider.security.faucet import FaucetClient


class DummyClient:
    class Eth:
        def __init__(self, bal):
            self._bal = bal
        async def get_balance(self, addr):
            return self._bal

    class HTTP:
        def __init__(self, bal):
            self.eth = DummyClient.Eth(bal)
        def from_wei(self, v, unit):
            return v / 10**18

    def __init__(self, bal):
        self._http = DummyClient.HTTP(bal)
    def http_client(self):
        return self._http


@pytest.mark.asyncio
async def test_faucet_skips_when_balance_sufficient(monkeypatch):
    fc = FaucetClient("https://f", "https://cap", "key")
    async def ensure():
        fc.client = DummyClient(bal=2 * 10**17)  # 0.2 ETH
    monkeypatch.setattr(fc, "_ensure_client", ensure)
    tx = await fc.get_funds("0xaddr")
    assert tx is None  # skipped


@pytest.mark.asyncio
async def test_faucet_happy_path(monkeypatch):
    fc = FaucetClient("https://f", "https://cap", "key")
    async def ensure():
        fc.client = DummyClient(bal=0)
    monkeypatch.setattr(fc, "_ensure_client", ensure)
    # Patch internal methods
    async def _get():
        return {"token": "t1", "challenge": [["salt", "00"]]}
    async def _redeem(token, sols):
        return "t2"
    async def _req(addr, tok):
        return "0xabc"
    monkeypatch.setattr(fc, "_get_challenge", _get)
    monkeypatch.setattr(fc, "_solve_challenge", lambda s, t: 0)
    monkeypatch.setattr(fc, "_redeem_solution", _redeem)
    monkeypatch.setattr(fc, "_request_faucet", _req)
    tx = await fc.get_funds("0xaddr")
    assert tx == "0xabc"


@pytest.mark.asyncio
async def test_faucet_invalid_challenge(monkeypatch):
    fc = FaucetClient("https://f", "https://cap", "key")
    async def ensure():
        fc.client = DummyClient(bal=0)
    monkeypatch.setattr(fc, "_ensure_client", ensure)
    monkeypatch.setattr(fc, "_get_challenge", lambda: {"bad": True})
    tx = await fc.get_funds("0xaddr")
    assert tx is None


@pytest.mark.asyncio
async def test_faucet_redeem_failure(monkeypatch):
    fc = FaucetClient("https://f", "https://cap", "key")
    async def ensure():
        fc.client = DummyClient(bal=0)
    monkeypatch.setattr(fc, "_ensure_client", ensure)
    monkeypatch.setattr(fc, "_get_challenge", lambda: {"token": "t1", "challenge": [["salt", "00"]]})
    monkeypatch.setattr(fc, "_solve_challenge", lambda s, t: 0)
    monkeypatch.setattr(fc, "_redeem_solution", lambda token, sols: None)
    tx = await fc.get_funds("0xaddr")
    assert tx is None


@pytest.mark.asyncio
async def test_faucet_request_failure(monkeypatch):
    fc = FaucetClient("https://f", "https://cap", "key")
    async def ensure():
        fc.client = DummyClient(bal=0)
    monkeypatch.setattr(fc, "_ensure_client", ensure)
    monkeypatch.setattr(fc, "_get_challenge", lambda: {"token": "t1", "challenge": [["salt", "00"]]})
    monkeypatch.setattr(fc, "_solve_challenge", lambda s, t: 0)
    monkeypatch.setattr(fc, "_redeem_solution", lambda token, sols: "t2")
    monkeypatch.setattr(fc, "_request_faucet", lambda addr, tok: None)
    tx = await fc.get_funds("0xaddr")
    assert tx is None
