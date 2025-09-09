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

            def topUp(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "topUp", **kwargs})

        self.functions = Funcs(self)


class DummyWeb3:
    HTTPProvider = staticmethod(lambda url: None)

    def __init__(self, _provider=None):
        self.eth = types.SimpleNamespace(
            default_account=None,
            get_transaction_count=lambda addr: 0,
            send_raw_transaction=lambda raw: types.SimpleNamespace(hex=lambda: "0xabc"),
            wait_for_transaction_receipt=lambda h: types.SimpleNamespace(status=1, logs=[{"data": "ok"}]),
            contract=lambda address=None, abi=None: DummyContract(),
            gas_price=1,
            chain_id=31337,
        )

    @staticmethod
    def to_checksum_address(addr):
        return addr


def _patch_env(monkeypatch, raw_field: str):
    from requestor.payments import blockchain_service as bs

    class Signed:
        def __init__(self):
            setattr(self, raw_field, b"\x01\x02")

    class Signer:
        def __init__(self):
            self.address = "0xme"

        def sign_transaction(self, tx):
            return Signed()

    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(bs, "Account", types.SimpleNamespace(from_key=lambda k: Signer()))


@pytest.mark.parametrize("field", ["rawTransaction", "raw_transaction"])  # support both web3 variants
def test_native_create_stream_supports_raw_fields(monkeypatch, field):
    _patch_env(monkeypatch, field)
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0x0000000000000000000000000000000000000000",  # native ETH
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    sid = client.create_stream("0xprov", 1000, 1)
    assert sid == 123


@pytest.mark.parametrize("field", ["rawTransaction", "raw_transaction"])  # support both web3 variants
def test_native_topup_supports_raw_fields(monkeypatch, field):
    _patch_env(monkeypatch, field)
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0x0000000000000000000000000000000000000000",  # native ETH
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    tx = client.top_up(42, 123)
    assert tx == "0xabc"

