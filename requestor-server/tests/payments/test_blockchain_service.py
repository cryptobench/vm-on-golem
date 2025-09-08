import types
import pytest

from requestor.payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig


class DummyContract:
    def __init__(self):
        self.address = "0xdead"
        class Events:
            def StreamCreated(self):
                class Ev:
                    def process_log(self, log):
                        return {"args": {"streamId": 123}}
                return Ev()
        self.events = Events()

        class Funcs:
            def __init__(self, outer):
                self.outer = outer
            def createStream(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "create", **kwargs})
            def withdraw(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "withdraw", **kwargs})
            def terminate(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "terminate", **kwargs})
            def topUp(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "topUp", **kwargs})
        self.functions = Funcs(self)


class DummyERC20:
    def __init__(self):
        class Funcs:
            def approve(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "approve", **kwargs})
        self.functions = Funcs()
        self.address = "0xglm"


class DummyWeb3:
    HTTPProvider = staticmethod(lambda url: None)
    def __init__(self, _provider=None):
        self.eth = types.SimpleNamespace(
            default_account=None,
            get_transaction_count=lambda addr: 0,
            send_transaction=lambda tx: types.SimpleNamespace(hex=lambda: "0xabc"),
            send_raw_transaction=lambda raw: types.SimpleNamespace(hex=lambda: "0xabc"),
            wait_for_transaction_receipt=lambda h: types.SimpleNamespace(status=1, logs=[{"data": "ok"}]),
            contract=lambda address=None, abi=None: DummyContract(),
        )
        self.middleware_onion = types.SimpleNamespace(add=lambda *a, **kw: None)
        self.contract = lambda address=None, abi=None: DummyContract()

    @staticmethod
    def to_checksum_address(addr):
        return addr


def test_create_stream_parses_event(monkeypatch):
    # Patch Web3 in module namespace
    from requestor.payments import blockchain_service as bs
    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(bs, "Account", types.SimpleNamespace(from_key=lambda k: types.SimpleNamespace(address="0xme")))
    # Patch ERC20 contract creation
    monkeypatch.setattr(bs, "ERC20_ABI", bs.ERC20_ABI)
    # Build client
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0xglm",
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    # Swap erc20 to dummy
    client.erc20 = DummyERC20()
    stream_id = client.create_stream("0xprov", 1000, 1)
    assert stream_id == 123


def test_create_stream_raises_when_no_event(monkeypatch):
    from requestor.payments import blockchain_service as bs

    class NoEventContract(DummyContract):
        def __init__(self):
            super().__init__()
            class Events:
                def StreamCreated(self):
                    class Ev:
                        def process_log(self, log):
                            raise ValueError("nope")
                    return Ev()
            self.events = Events()

    class W(DummyWeb3):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            # override eth.contract to return NoEventContract
            self.eth = types.SimpleNamespace(
                default_account=None,
                get_transaction_count=lambda addr: 0,
                send_transaction=lambda tx: types.SimpleNamespace(hex=lambda: "0xabc"),
                send_raw_transaction=lambda raw: types.SimpleNamespace(hex=lambda: "0xabc"),
                wait_for_transaction_receipt=lambda h: types.SimpleNamespace(status=1, logs=[{"data": "ok"}]),
                contract=lambda address=None, abi=None: NoEventContract(),
            )

    monkeypatch.setattr(bs, "Web3", W)
    monkeypatch.setattr(bs, "Account", types.SimpleNamespace(from_key=lambda k: types.SimpleNamespace(address="0xme")))
    cfg = StreamPaymentConfig("http://localhost", "0xcontract", "0xglm", "0x01")
    client = StreamPaymentClient(cfg)
    client.erc20 = DummyERC20()
    with pytest.raises(RuntimeError):
        client.create_stream("0xprov", 1000, 1)


def test_top_up_happy_path(monkeypatch):
    from requestor.payments import blockchain_service as bs
    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(bs, "Account", types.SimpleNamespace(from_key=lambda k: types.SimpleNamespace(address="0xme")))
    cfg = StreamPaymentConfig("http://localhost", "0xcontract", "0xglm", "0x01")
    client = StreamPaymentClient(cfg)
    client.erc20 = DummyERC20()
    tx = client.top_up(42, 12345)
    assert tx == "0xabc"
