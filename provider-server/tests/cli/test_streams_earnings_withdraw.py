import types


class FakeStreamMap:
    def __init__(self, mapping):
        self._mapping = mapping
    async def all_items(self):
        return dict(self._mapping)
    async def get(self, vm_id):
        return self._mapping.get(vm_id)


def test_streams_earnings_json(monkeypatch):
    # Fake Container returning our stream_map, not used for reader here
    class FakeContainer:
        def __init__(self):
            self.config = types.SimpleNamespace(from_pydantic=lambda *_: None)
        def stream_map(self):
            return FakeStreamMap({"vm-1": 1, "vm-2": 2})

    # Fake reader with fixed now and two streams
    class FakeReader:
        def __init__(self, *_):
            self._now = 1_000_000
            self.web3 = types.SimpleNamespace(eth=types.SimpleNamespace(get_block=lambda _: {"timestamp": self._now}))
        def get_stream(self, sid):
            # token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted
            if int(sid) == 1:
                return {
                    "token": "0x0",
                    "sender": "0xreq",
                    "recipient": "0xprov",
                    "startTime": self._now - 2000,
                    "stopTime": self._now + 1000,
                    "ratePerSecond": 10,
                    "deposit": 0,
                    "withdrawn": 5000,
                    "halted": False,
                }
            return {
                "token": "0x0",
                "sender": "0xreq",
                "recipient": "0xprov",
                "startTime": self._now - 500,
                "stopTime": self._now + 500,
                "ratePerSecond": 20,
                "deposit": 0,
                "withdrawn": 0,
                "halted": False,
            }

    # Patch Container and Reader used by implementation
    import provider.main as m
    import provider.container as cont
    from provider.main import streams_earnings
    monkeypatch.setattr(cont, "Container", FakeContainer)
    # Patch the class in the module path it’s imported from inside the function
    import provider.payments.blockchain_service as b
    monkeypatch.setattr(b, "StreamPaymentReader", FakeReader)

    # Call function directly and capture output
    import io, sys, json
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        streams_earnings(json_out=True)
    finally:
        sys.stdout = old
    data = json.loads(buf.getvalue())
    assert "streams" in data and "totals" in data
    assert data["totals"]["withdrawable"] >= 0


def test_streams_withdraw_all_and_single(monkeypatch):
    # Fake Container for withdraw path
    class FakeContainer:
        def __init__(self):
            self.config = types.SimpleNamespace(from_pydantic=lambda *_: None)
        def stream_map(self):
            return FakeStreamMap({"vm-1": 1, "vm-2": 2})
        def stream_client(self):
            class C:
                def __init__(self):
                    self.calls = []
                def withdraw(self, sid):
                    self.calls.append(int(sid))
                    return f"0xdead{sid}"
            return C()

    import provider.main as m
    import provider.container as cont
    from provider.main import streams_withdraw
    monkeypatch.setattr(cont, "Container", FakeContainer)

    import io, sys
    # Withdraw all
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        streams_withdraw(vm_id=None, all_streams=True)
    finally:
        sys.stdout = old
    assert "Withdrew stream" in buf.getvalue()
    # Withdraw single
    buf2 = io.StringIO()
    sys.stdout = buf2
    try:
        streams_withdraw(vm_id="vm-2", all_streams=False)
    finally:
        sys.stdout = old
    assert "vm-2" in buf2.getvalue()
