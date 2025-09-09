import types

from requestor.payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig


class DummyERC20:
    def __init__(self):
        class Funcs:
            def allowance(self, *a, **k):
                return types.SimpleNamespace(call=lambda: 0)

            def approve(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "approve", **kwargs})

        self.functions = Funcs()


class DummyContract:
    def __init__(self):
        self.address = "0xstream"
        class Funcs:
            def topUp(self, *args):
                return types.SimpleNamespace(build_transaction=lambda kwargs: {"to": "topUp", **kwargs})

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
            max_priority_fee=None,
            send_raw_transaction=lambda raw: types.SimpleNamespace(hex=lambda: "0xabc"),
            wait_for_transaction_receipt=lambda h: types.SimpleNamespace(status=1, logs=[{"data": "ok"}]),
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
            assert "gas" in tx or "gasPrice" in tx or "maxFeePerGas" in tx
            return Signed()

    monkeypatch.setattr(bs, "Web3", DummyWeb3)
    monkeypatch.setattr(bs, "Account", types.SimpleNamespace(from_key=lambda k: Signer()))
    # Ensure ERC20 path
    monkeypatch.setattr(bs, "ERC20_ABI", bs.ERC20_ABI)

    cfg = StreamPaymentConfig(
        rpc_url="http://localhost",
        contract_address="0xcontract",
        glm_token_address="0xglm",  # ERC20
        private_key="0x01",
    )
    client = StreamPaymentClient(cfg)
    # inject dummy erc20
    client.erc20 = DummyERC20()
    tx = client.top_up(1, 123)
    assert tx == "0xabc"
