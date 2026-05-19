from golem_faucet import _tx_hash_from_faucet_line


def test_tx_hash_from_plain_json():
    assert _tx_hash_from_faucet_line('{"txHash":"0xabc"}') == "0xabc"


def test_tx_hash_from_sse_json():
    assert (
        _tx_hash_from_faucet_line('data: {"stage":"mining","txHash":"0xabc"}')
        == "0xabc"
    )


def test_tx_hash_from_non_data_line():
    assert _tx_hash_from_faucet_line("event: progress") is None
