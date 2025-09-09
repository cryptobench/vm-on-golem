import pytest

from provider.security.l2_faucet import L2FaucetService


class DummyWeb3:
    HTTPProvider = staticmethod(lambda url: None)
    def __init__(self, bal_wei: int):
        self._bal = bal_wei
        class Eth:
            pass
        self.eth = Eth()
        self.eth.get_balance = lambda addr: bal_wei
    @staticmethod
    def to_checksum_address(a):
        return a
    @staticmethod
    def from_wei(v, unit):
        return v / 10**18


class DummyClient:
    def __init__(self, chall=None, redeemed=None, tx=None):
        self._chall = chall
        self._redeemed = redeemed
        self._tx = tx
    async def get_challenge(self):
        return self._chall
    async def redeem(self, token, sols):
        return self._redeemed
    async def request_funds(self, address, token):
        return self._tx


class DummyCfg:
    POLYGON_RPC_URL = "http://localhost"
    L2_FAUCET_URL = "https://l2.holesky.golemdb.io/faucet"
    L2_CAPTCHA_URL = "https://cap.gobas.me"
    L2_CAPTCHA_API_KEY = "05381a2cef5e"


@pytest.mark.asyncio
async def test_l2_faucet_skip_on_sufficient_balance(monkeypatch):
    from provider.security import l2_faucet as mod
    monkeypatch.setattr(mod, "Web3", DummyWeb3)
    svc = L2FaucetService(DummyCfg())
    tx = await svc.request_funds("0xaddr")
    # default DummyWeb3 returns 0; set high balance
    svc.web3 = DummyWeb3(2 * 10**17)
    tx = await svc.request_funds("0xaddr")
    assert tx is None


@pytest.mark.asyncio
async def test_l2_faucet_happy_path(monkeypatch):
    from provider.security import l2_faucet as mod
    class W:
        HTTPProvider = staticmethod(lambda url: None)
        def __call__(self, *_a, **_k):
            return DummyWeb3(0)
    monkeypatch.setattr(mod, "Web3", W())
    svc = L2FaucetService(DummyCfg())
    # Inject dummy client
    svc.client = DummyClient(
        chall={"token": "t1", "challenge": [["salt", "00"]]},
        redeemed="t2",
        tx="0xabc",
    )
    tx = await svc.request_funds("0xaddr")
    assert tx == "0xabc"


@pytest.mark.asyncio
async def test_l2_faucet_challenge_failure(monkeypatch):
    from provider.security import l2_faucet as mod
    class W:
        HTTPProvider = staticmethod(lambda url: None)
        def __call__(self, *_a, **_k):
            return DummyWeb3(0)
    monkeypatch.setattr(mod, "Web3", W())
    svc = L2FaucetService(DummyCfg())
    svc.client = DummyClient(chall=None)
    tx = await svc.request_funds("0xaddr")
    assert tx is None


@pytest.mark.asyncio
async def test_l2_faucet_redeem_failure(monkeypatch):
    from provider.security import l2_faucet as mod
    class W:
        HTTPProvider = staticmethod(lambda url: None)
        def __call__(self, *_a, **_k):
            return DummyWeb3(0)
    monkeypatch.setattr(mod, "Web3", W())
    svc = L2FaucetService(DummyCfg())
    svc.client = DummyClient(chall={"token": "t1", "challenge": [["salt", "00"]]}, redeemed=None)
    tx = await svc.request_funds("0xaddr")
    assert tx is None


@pytest.mark.asyncio
async def test_l2_faucet_faucet_failure(monkeypatch):
    from provider.security import l2_faucet as mod
    class W:
        HTTPProvider = staticmethod(lambda url: None)
        def __call__(self, *_a, **_k):
            return DummyWeb3(0)
    monkeypatch.setattr(mod, "Web3", W())
    svc = L2FaucetService(DummyCfg())
    svc.client = DummyClient(
        chall={"token": "t1", "challenge": [["salt", "00"]]},
        redeemed="t2",
        tx=None,
    )
    tx = await svc.request_funds("0xaddr")
    assert tx is None

