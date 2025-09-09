import types

import pytest

from provider.payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig


class DummyContract:
    def __init__(self):
        class Funcs:
            def withdraw(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "withdraw", **kwargs})
        self.functions = Funcs()


class DummyWeb3:
    HTTPProvider = staticmethod(lambda url: None)

    def __init__(self, _provider=None):
        self.eth = types.SimpleNamespace(
            default_account=None,
            get_transaction_count=lambda addr: 0,
            send_raw_transaction=lambda raw: types.SimpleNamespace(hex=lambda: "0xabc"),
            wait_for_transaction_receipt=lambda h: types.SimpleNamespace(status=1),
            contract=lambda address=None, abi=None: DummyContract(),
        )

    @staticmethod
    def to_checksum_address(addr):
        return addr


def _patch_env(monkeypatch, raw_field: str):
    from provider.payments import blockchain_service as bs

    class Signed:
        def __init__(self):
            setattr(self, raw_field, b"\x00\x01")

    class Signer:
        def __init__(self):
            self.address = "0xme"

        def sign_transaction(self, tx):
            return Signed()

    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(bs, "Account", types.SimpleNamespace(from_key=lambda k: Signer()))


@pytest.mark.parametrize("field", ["rawTransaction", "raw_transaction"])  # support both web3 variants
def test_withdraw_supports_raw_fields(monkeypatch, field):
    _patch_env(monkeypatch, field)
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    tx = client.withdraw(42)
    assert len(tx) > 0

