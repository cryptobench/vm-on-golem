from requestor.payments.blockchain_service import STREAM_PAYMENT_ABI


def test_stream_payment_abi_has_streams_and_topup():
    names = {entry.get('name') for entry in STREAM_PAYMENT_ABI if entry.get('type') == 'function'}
    assert 'streams' in names
    assert 'topUp' in names

