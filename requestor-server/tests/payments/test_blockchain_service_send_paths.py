import types

from requestor.payments.blockchain_service import (
    StreamPaymentClient,
    StreamPaymentConfig,
)


class DummyContract:
    def __init__(self):
        self.address = "0xstream"

        class Funcs:
            def topUp(self, *args):
                return types.SimpleNamespace(
                    build_transaction=lambda kwargs: {"to": "topUp", **kwargs}
                )

            def allowance(self, *args):
                return types.SimpleNamespace(call=lambda: 0)

            def approve(self, *args):
                return types.SimpleNamespace(
                    build_transaction=lambda kwargs: {"to": "approve", **kwargs}
                )

        self.functions = Funcs()

        class Events:
            def StreamCreated(self):
                class Ev:
                    def process_log(self, log):
                        return {"args": {"streamId": 1}}

                return Ev()

        self.events = Events()


class DummyWeb3:
    HTTPProvider = staticmethod(lambda url: None)

    def __init__(self, _provider=None):
        self.eth = types.SimpleNamespace(
            default_account=None,
            get_transaction_count=lambda addr: 0,
            estimate_gas=lambda tx: 21000,
            gas_price=42,
            chain_id=31337,
            max_priority_fee=1,
            send_raw_transaction=lambda raw: types.SimpleNamespace(hex=lambda: "0xabc"),
            wait_for_transaction_receipt=lambda h: types.SimpleNamespace(
                status=1, logs=[{"data": "ok"}]
            ),
            contract=lambda address=None, abi=None: DummyContract(),
        )

    @staticmethod
    def to_checksum_address(addr):
        return addr


def test_send_path_eip1559_and_gas_estimation(monkeypatch):
    from requestor.payments import blockchain_service as bs

    class Signed:
        rawTransaction = b"\x01\x02"

    class Signer:
        def __init__(self):
            self.address = "0xme"

        def sign_transaction(self, tx):
            # ensure gas fields were attached
            assert tx["gas"] == 21000
            assert tx["maxPriorityFeePerGas"] == 1
            assert tx["maxFeePerGas"] == 42
            assert "gasPrice" not in tx
            return Signed()

    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(
        bs, "Account", types.SimpleNamespace(from_key=lambda k: Signer())
    )
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0x1111111111111111111111111111111111111111",
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    tx = client.top_up(1, 123)
    assert tx == "0xabc"


def test_send_path_uses_legacy_gas_price_when_eip1559_unavailable(monkeypatch):
    from requestor.payments import blockchain_service as bs

    signed_txs = []

    class LegacyWeb3(DummyWeb3):
        def __init__(self, _provider=None):
            super().__init__(_provider)
            self.eth = types.SimpleNamespace(
                default_account=None,
                get_transaction_count=lambda addr: 0,
                estimate_gas=lambda tx: 21000,
                gas_price=42,
                chain_id=31337,
                send_raw_transaction=lambda raw: types.SimpleNamespace(
                    hex=lambda: "0xabc"
                ),
                wait_for_transaction_receipt=lambda h: types.SimpleNamespace(
                    status=1, logs=[{"data": "ok"}]
                ),
                contract=lambda address=None, abi=None: DummyContract(),
            )

    class Signed:
        rawTransaction = b"\x01\x02"

    class Signer:
        def __init__(self):
            self.address = "0xme"

        def sign_transaction(self, tx):
            signed_txs.append(tx)
            return Signed()

    monkeypatch.setattr(bs, "Web3", LegacyWeb3)
    monkeypatch.setattr(
        bs, "Account", types.SimpleNamespace(from_key=lambda k: Signer())
    )
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0x1111111111111111111111111111111111111111",
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    tx = client.top_up(1, 123)

    assert tx == "0xabc"
    assert signed_txs
    for signed_tx in signed_txs:
        assert signed_tx["gasPrice"] == 42
        assert "maxFeePerGas" not in signed_tx
        assert "maxPriorityFeePerGas" not in signed_tx


def test_send_path_rejects_mixed_fee_fields(monkeypatch):
    from requestor.payments import blockchain_service as bs

    class Signer:
        address = "0xme"

        def sign_transaction(self, tx):
            raise AssertionError("conflicting transaction should not be signed")

    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(
        bs, "Account", types.SimpleNamespace(from_key=lambda k: Signer())
    )
    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0x1111111111111111111111111111111111111111",
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    fn = client.contract.functions.topUp(1, 123)

    try:
        client._send(fn, {"gasPrice": 1, "maxFeePerGas": 2})
    except ValueError as exc:
        assert "cannot mix gasPrice" in str(exc)
    else:
        raise AssertionError("expected conflicting gas fields to fail")
